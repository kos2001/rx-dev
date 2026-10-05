// Read-only navigation and native-media verification: never starts a job.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
  await fs.mkdir('outputs/dashboard',{recursive:true});
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
    const errors=[],writes=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()==='POST')writes.push(r.url());});
    await page.goto('http://127.0.0.1:3030');
    await page.locator('.success-card').first().waitFor();
    await page.locator('#connectionText').filter({hasText:'백엔드 연결됨'}).waitFor();
    await page.locator('.scene-preview img').evaluate(image=>image.decode());
    assert.equal(await page.locator('.solution-card').count(),3);
    await page.screenshot({path:'outputs/dashboard/platform-desktop.png'});
    await page.screenshot({path:'outputs/dashboard/platform-full.png',fullPage:true});
    await page.locator('.hero-primary').click();
    await page.locator('#trainingView:visible').waitFor();
    assert.equal(await page.locator('.workspace-steps button').count(),4);
    assert.equal(await page.locator('#simulationLaunch').isVisible(),false);
    await page.screenshot({path:'outputs/dashboard/platform-training-desktop.png'});
    for(const algorithm of ['act','diffusion','ppo','sac']){
      await page.locator('[data-view="dashboard"]').click();
      await page.locator(`[data-algorithm="${algorithm}"]`).click();
      assert.equal(await page.locator('#trainingAlgorithm').inputValue(),algorithm);
      assert.equal(await page.locator('#trainingMode').inputValue(),'new');
    }
    await page.locator('[data-view="dashboard"]').click();
    await page.locator('[data-target="learningWorkspace"]').click();
    assert.equal(await page.locator('#learningWorkspace').isVisible(),true);
    assert.equal(await page.evaluate(()=>document.activeElement.id),'learningWorkspace');
    await page.locator('[data-view="dashboard"]').click();
    await page.locator('[data-target="evaluationWorkspace"]').click();
    assert.equal(await page.evaluate(()=>document.activeElement.id),'evaluationWorkspace');
    await page.locator('[data-view="dashboard"]').click();
    await page.locator('.scene-preview').click();
    assert.equal(await page.evaluate(()=>document.activeElement.id),'successShowcase');
    const video=page.locator('.success-card video').first();
    assert.equal(await video.evaluate(v=>v.paused),false,'Hero preview should start the native recording');
    await page.waitForFunction(()=>document.querySelector('.success-card video').currentTime>0.2);
    await video.evaluate(v=>v.pause());
    for(const width of [1024,768,390,360]){
      await page.setViewportSize({width,height:844});
      await page.evaluate(()=>window.scrollTo(0,0));
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow at ${width}px`);
      await page.screenshot({path:`outputs/dashboard/platform-${width}.png`});
    }
    await page.locator('.hero-primary').click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Training overflow');
    await page.screenshot({path:'outputs/dashboard/platform-training-mobile.png'});
    await page.locator('[data-view="examples"]').click();
    assert.equal(await page.locator('.example-card').count(),7);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Library overflow');
    await page.locator('[data-example="transfer"]').click();
    assert.equal(await page.locator('#experiment').inputValue(),'transfer');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'experiment');
    assert.deepEqual(writes,[]);
    assert.deepEqual(errors,[]);
    console.log('Platform: all learning routes, agent/evaluation navigation, native video playback, 4 responsive widths and no job submissions passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
