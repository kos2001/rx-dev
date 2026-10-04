// Synthetic API fixture: verifies UI and recovery requests, not simulator outcomes.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const arm={successes:1,episodes:3,success_interval_95:[.06,.79],mean_best_reward:1.3};
    let state={id:'f'.repeat(32),harness_version:1,status:'completed',stage:'completed',algorithm:'act',
      skills:{},roles:{},children:{},baseline_config:{environment:'transfer'},training_seed:500000,
      runtime_versions:{lerobot:'fixture'},checkpoint_receipts:{baseline:[],candidate:[]},
      events:[{stage:'preflight',at:1},{stage:'counterexample_verification',at:2}],
      holdout:{seeds:[41000,41001,41002],baseline:arm,candidate:arm},
      decision:{verdict:'inconclusive',paired_p_value:1},verification:{holdout:{valid:true,retention_verified:false,issues:[],
        resolver:{success_gains:1,success_losses:1,regression_seeds:[41000]},
        challenger:{shared_failure_seeds:[41002],retention_failures:[{arm:'candidate',seed:41001}],missing_terminal_evidence:[],reward_only_improvement:false}}}};
    let resumed=false;
    await page.route('http://127.0.0.1:8787/api/learning-agents/**',async route=>{
      if(route.request().url().endsWith('/resume')){
        assert.deepEqual(route.request().postDataJSON(),{job_id:state.id});resumed=true;
        state={...state,status:'running',stage:'holdout_candidate'};
      }
      await route.fulfill({status:route.request().method()==='POST'?202:200,json:state});
    });
    await page.route('http://127.0.0.1:8787/api/agents/health',route=>route.fulfill({json:{connected:true}}));
    await page.goto('http://127.0.0.1:3030');
    await page.locator('[data-view="training"]').click();
    await page.locator('.harness-evidence').waitFor();
    assert.match(await page.locator('.harness-evidence').textContent(),/결론 유보/);
    assert.match(await page.locator('.harness-evidence').textContent(),/퇴행 Seed: 41000/);
    assert.match(await page.locator('.harness-evidence').textContent(),/candidate · 41001/);
    assert.equal(await page.locator('#learningAgentHoldout').inputValue(),'10');
    assert.equal(await page.locator('#learningAgentLimit').getAttribute('max'),'400');
    await page.locator('.harness-evidence').scrollIntoViewIfNeeded();
    await page.screenshot({path:'outputs/dashboard/learning-harness-desktop.png'});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.locator('.harness-evidence').scrollIntoViewIfNeeded();
    await page.locator('.harness-evidence').screenshot({path:'outputs/dashboard/learning-harness-mobile.png'});
    state={...state,status:'interrupted'};
    await page.reload();await page.locator('[data-view="training"]').click();
    await page.locator('#learningAgentResume:visible').waitFor();
    await page.locator('#learningAgentResume').click();
    await page.waitForFunction(()=>document.getElementById('learningAgentStatus').textContent.includes('후보 최종 평가'));
    assert.ok(resumed);assert.ok(await page.locator('#trainingStart').isDisabled());
    assert.deepEqual(errors,[]);
    console.log('Synthetic harness UI: final evidence, retention counterexample, recovery request and mobile layout passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
