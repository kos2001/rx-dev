// Live read-only records; synthetic requests test serialization without starting jobs.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
  await fs.mkdir('outputs/dashboard',{recursive:true});
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
    const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()==='POST')writes.push(r.url());});
    await page.goto('http://127.0.0.1:3030');await page.locator('[data-view="training"]').click();
    await page.locator('#trainingStart:enabled').waitFor();
    await page.locator('#trainingRecordCount').filter({hasText:/^\d+$/}).waitFor();
    const history=await page.request.get('http://127.0.0.1:8787/api/training').then(r=>r.json());
    const evaluations=history.filter(j=>j.evaluation);
    assert.equal(Number(await page.locator('#trainingRecordCount').textContent()),history.filter(j=>j.kind!=='evaluation').length);
    assert.equal(Number(await page.locator('#evaluationRecordCount').textContent()),evaluations.length);
    assert.equal(await page.locator('#trainingForm .config-card').count(),3);
    assert.equal(await page.locator('.agent-role-card').count(),3);
    assert.equal(await page.locator('.evaluation-result-card').count(),Math.min(6,evaluations.length));
    const first=evaluations[0];
    if(first){
      const card=page.locator('.evaluation-result-card').first();
      assert.equal(Number(await card.locator('[role="meter"]').getAttribute('aria-valuenow')),Number((first.evaluation.success_rate*100).toFixed(1)));
      await card.locator('summary').click();
      const video=card.locator('video').first();
      if(await video.count()){
        await video.evaluate(async v=>{v.muted=true;await v.play();});
        await page.waitForFunction(()=>document.querySelector('.evaluation-card-meta video')?.currentTime>0.05);
        await video.evaluate(v=>v.dataset.keepCard='yes');
        await page.waitForTimeout(2300);
        assert.equal(await video.getAttribute('data-keep-card'),'yes');await video.evaluate(v=>v.pause());
      }
    }
    await page.locator('#trainingHistoryFilter').selectOption('training');
    assert.ok(await page.locator('[data-policy-eval]').count());
    if(first?.videos?.length)assert.equal(await page.locator('.evaluation-card-meta video').first().getAttribute('data-keep-card'),'yes');
    await page.locator('#trainingHistoryFilter').selectOption('evaluation');
    assert.equal(await page.locator('#trainingHistory [data-policy-eval]').count(),0);
    await page.locator('#trainingHistoryFilter').selectOption('all');
    await page.locator('#trainingHistorySearch').fill(history.at(-1).id);
    assert.equal(await page.locator('.history-record-card').count(),1);
    assert.equal(await page.locator('.history-record-card').getAttribute('data-record-id'),history.at(-1).id);
    await page.locator('#trainingHistorySearch').fill('no-record-matches-this');
    assert.match(await page.locator('#trainingHistory').textContent(),/표시할 기록이 없습니다/);
    await page.locator('#trainingHistorySearch').fill('');
    if(history.length>6){await page.locator('#trainingHistoryMore').click();assert.equal(await page.locator('.history-record-card').count(),Math.min(12,history.length));}
    for(const algorithm of ['ppo','sac','diffusion','act']){
      await page.locator('#trainingAlgorithm').selectOption(algorithm);
      const rl=['ppo','sac'].includes(algorithm);
      assert.equal(await page.locator('#experienceSignal').isVisible(),rl);
      assert.equal(await page.locator('#trainingDataset').isDisabled(),rl);
      assert.equal(await page.locator('#trainingRolloutLabel').isVisible(),algorithm==='ppo');
    }
    await page.locator('#trainingMode').selectOption('resume');
    assert.equal(await page.locator('#trainingDataset').isDisabled(),true);
    assert.equal(await page.locator('#trainingBatch').isDisabled(),true);
    await page.locator('#trainingMode').selectOption('new');
    await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'outputs/dashboard/learning-cards-desktop.png'});
    await page.locator('#evaluationWorkspace').screenshot({path:'outputs/dashboard/evaluation-cards-desktop.png'});
    await page.locator('#learningWorkspace').screenshot({path:'outputs/dashboard/agent-cards-desktop.png'});
    await page.locator('#trainingArchive').screenshot({path:'outputs/dashboard/history-cards-desktop.png'});
    for(const width of [1024,768,390,360]){
      await page.setViewportSize({width,height:844});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow at ${width}`);
      if(width===390){await page.locator('#trainingConfiguration').screenshot({path:'outputs/dashboard/learning-cards-mobile.png'});await page.locator('#learningWorkspace').screenshot({path:'outputs/dashboard/agent-cards-mobile.png'});}
    }
    assert.deepEqual(writes,[]);
    // Intercept writes before exercising submit buttons: no trainer/provider is invoked.
    let submitted;
    await page.route('http://127.0.0.1:8787/api/training',async route=>{
      if(route.request().method()!=='POST')return route.continue();
      submitted=route.request().postDataJSON();await route.fulfill({status:202,json:{status:'idle'}});
    });
    for(const algorithm of ['act','diffusion','ppo','sac']){
      await page.locator('#trainingAlgorithm').selectOption(algorithm);
      await page.locator('#trainingEnvironment').selectOption('transfer');
      await page.locator('#trainingSteps').fill(['act','diffusion'].includes(algorithm)?'1':algorithm==='ppo'?'128':'64');
      await page.locator('#trainingBatch').fill(['act','diffusion'].includes(algorithm)?'1':'8');
      if(['act','diffusion'].includes(algorithm))await page.locator('#trainingEpisodes').fill('1');
      await page.locator('#trainingStart:enabled').waitFor();
      const response=page.waitForResponse(r=>r.url().endsWith('/api/training') && r.request().method()==='POST');
      await page.locator('#trainingStart').click();await response;
      assert.equal(submitted.algorithm,algorithm);assert.equal(submitted.environment,'transfer');
      assert.equal(submitted.mode,'new');assert.equal(submitted.device,'cpu');
      if(['act','diffusion'].includes(algorithm))assert.equal(submitted.dataset,'lerobot/aloha_sim_transfer_cube_scripted');
      else{assert.equal(submitted.rollout_steps,128);assert.ok(submitted.learning_rate>0);assert.equal('dataset' in submitted,false);}
    }
    await page.route('http://127.0.0.1:8787/api/learning-agents',async route=>{
      submitted=route.request().postDataJSON();await route.fulfill({status:202,json:{status:'idle'}});
    });
    await page.locator('#learningAgentEpisodes').fill('2');await page.locator('#learningAgentHoldout').fill('3');
    await page.locator('#learningAgentLimit').fill('200');
    await page.locator('#learningAgentStart:enabled').waitFor();
    const launched=page.waitForResponse(r=>r.url().endsWith('/api/learning-agents') && r.request().method()==='POST');
    await page.locator('#learningAgentStart').click();await launched;
    assert.equal(submitted.eval_episodes,2);assert.equal(submitted.holdout_episodes,3);assert.equal(submitted.step_limit,200);
    assert.equal(submitted.source_job.length,32);
    assert.deepEqual(errors,[]);
    console.log('Learning cards: live record counts/meters, playback survives polling, filters/search/load-more, RL/resume controls four responsive widths and intercepted form submissions passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
