// Real saved LIBERO jobs. Read-only: no training or provider submissions.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
  await fs.mkdir('outputs/dashboard',{recursive:true});
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    const errors=[],writes=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()==='POST')writes.push(r.url());});
    await page.goto('http://127.0.0.1:3030');
    await page.locator('#connectionText').filter({hasText:'백엔드 연결됨'}).waitFor();
    await page.locator('[data-view="training"]').click();
    await page.locator('#trainingMethodInfo').filter({hasText:'LeRobot'}).waitFor();
    await page.locator('#trainingEnvironment').selectOption('libero_drawer');
    assert.equal(await page.locator('#trainingDataset').inputValue(),'lerobot/libero');
    assert.equal(await page.locator('#trainingDataset').isDisabled(),true);
    assert.equal(await page.locator('#trainingAlgorithm option[value="ppo"]').evaluate(option=>option.disabled),true);
    assert.equal(await page.locator('[data-lesson-method="sac"]').isDisabled(),true);
    assert.equal(await page.locator('#trainingEpisodes').getAttribute('max'),'40');
    await page.locator('#trainingAlgorithm').selectOption('diffusion');
    await page.locator('#trainingEnvironment').selectOption('libero_basket');
    assert.match(await page.locator('#trainingMethodInfo').textContent(),/바구니/);
    assert.match(await page.locator('#trainingNotes').textContent(),/선택한 과제의 시연만/);
    assert.equal(await page.locator('#trainingAlgorithm').inputValue(),'diffusion');
    const history=await page.request.get('http://127.0.0.1:8787/api/training').then(r=>r.json());
    const source=history.find(j=>j.policy==='act' && j.config.environment==='libero_drawer' && j.status==='completed' && j.kind!=='evaluation');
    assert.ok(source?.demonstrations?.episode_indices.length);
    await page.locator('#learningAgentSource').selectOption(source.id);
    assert.match(await page.locator('#learningAgentSource option:checked').textContent(),/LIBERO/);
    assert.equal(await page.locator('#learningAgentStart').isEnabled(),true);
    const evaluation=history.find(j=>j.evaluation && j.config.environment==='libero_basket');
    assert.ok(evaluation);assert.equal(evaluation.evaluation.initialization_count,50);
    const video=await page.request.get('http://127.0.0.1:8787'+evaluation.videos[0]);assert.equal(video.status(),200);
    await page.locator('#trainingConfiguration').screenshot({path:'outputs/dashboard/libero-learning-desktop.png'});
    await page.locator('#learningWorkspace').screenshot({path:'outputs/dashboard/libero-agents-desktop.png'});
    for(const width of [1024,768,390,360]){
      await page.setViewportSize({width,height:844});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow at ${width}`);
      if(width===390)await page.locator('#trainingConfiguration').screenshot({path:'outputs/dashboard/libero-learning-mobile.png'});
    }
    await page.locator('[data-view="examples"]').click();
    const card=page.locator('.example-card').filter({has:page.getByRole('heading',{name:'LIBERO',exact:true})});
    await card.locator('summary').click();
    await card.locator('.libero-learning-link').click();
    assert.equal(await page.locator('#trainingView').isVisible(),true);
    assert.equal(await page.locator('#trainingEnvironment').inputValue(),'libero_drawer');
    await page.locator('#trainingEnvironment').selectOption('pusht');
    assert.equal(await page.locator('#trainingAlgorithm option[value="ppo"]').evaluate(option=>option.disabled),false);
    assert.equal(await page.locator('#trainingDataset').isDisabled(),false);
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    console.log('LIBERO learning: real records, task/method contracts, Agent source selection, evaluation media, responsive layout and catalog navigation passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
