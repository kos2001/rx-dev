const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const testApi='http://127.0.0.1:8787';
    await page.goto('http://127.0.0.1:3030');
    await page.locator('[data-view="training"]').click();
    let started;
    if(process.env.RX_LEARNING_JOB){
      started=await page.request.get(`${testApi}/api/learning-agents/current`).then(r=>r.json());
      assert.equal(started.id,process.env.RX_LEARNING_JOB);
    }else{
    await page.locator('#learningAgentStart:enabled').waitFor({timeout:30000});
    const history=await page.request.get(`${testApi}/api/training`).then(r=>r.json());
    const algorithm=process.env.RX_LEARNING_ALGORITHM || 'act';
    const source=history.find(j=>j.policy===algorithm && (!process.env.RX_LEARNING_ENV || j.config.environment===process.env.RX_LEARNING_ENV) && j.status==='completed' && j.kind!=='evaluation' && j.checkpoints.length);
    assert.ok(source);
    await page.locator('#learningAgentSource').selectOption(source.id);
    await page.locator('#learningAgentSteps').fill(algorithm==='ppo'?'128':algorithm==='sac'?'64':'1');
    await page.locator('#learningAgentEpisodes').fill('1');
    await page.locator('#learningAgentLimit').fill('10');
    const launch=page.waitForResponse(r=>r.url().endsWith('/api/learning-agents')&&r.request().method()==='POST');
    await page.locator('#learningAgentStart').click();
    const response=await launch;assert.equal(response.status(),202);
    started=await response.json();console.log('Started learning workflow',started.id);
    }
    if(started.status==='running'){
    await page.locator('#learningAgentStop:visible').waitFor();
    await page.locator('#trainingStart:disabled').waitFor();
    assert.equal(await page.locator('#trainingStart').isDisabled(),true);
    const blocked=await page.request.post(`${testApi}/api/training/stop`,{data:{}});
    assert.equal(blocked.status(),409);
    }
    const deadline=Date.now()+600000;
    let state;
    while(Date.now()<deadline){
      state=await page.request.get(`${testApi}/api/learning-agents/current`).then(r=>r.json());
      if(state.status!=='running')break;
      await page.waitForTimeout(2000);
    }
    assert.equal(state.status,'completed',JSON.stringify({stage:state.stage,error:state.error}));
    assert.equal(Object.keys(state.roles).length,3);
    assert.equal(new Set(Object.values(state.roles).map(r=>r.run_id)).size,3);
    assert.equal(Object.keys(state.children).length,4);
    assert.equal(state.roles.learning_reviewer.output.verdict,state.comparison.measured_verdict);
    assert.deepEqual(state.comparison.seeds,state.evaluation_seeds);
    await page.locator('#learningAgentStatus').filter({hasText:'실험 완료'}).waitFor();
    await page.locator('#learningAgentResults').scrollIntoViewIfNeeded();
    await page.screenshot({path:'outputs/dashboard/learning-agents-desktop.png',fullPage:false});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:'outputs/dashboard/learning-agents-mobile.png',fullPage:false});
    assert.deepEqual(errors,[]);
    console.log('Actual Hermes roles: paired real training/evaluation, measured review, work lock and mobile UI passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
