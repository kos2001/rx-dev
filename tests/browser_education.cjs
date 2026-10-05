// Read-only UI verification: concept examples never replace measured outcomes.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
  await fs.mkdir('outputs/dashboard',{recursive:true});
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
    const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')writes.push(r.url());});
    await page.goto('http://127.0.0.1:3030');
    await page.locator('[data-view="training"]').click();await page.locator('#trainingStart:enabled').waitFor();
    assert.equal(await page.locator('.learning-path').count(),2);
    assert.equal(await page.locator('.metric-guide article').count(),3);
    assert.equal(await page.locator('.agent-teaching-flow article').count(),3);
    const descriptions={act:/행동 묶음/,diffusion:/잡음/,ppo:/변화 제한/,sac:/다양성/};
    for(const method of ['act','diffusion','ppo','sac']){
      await page.locator(`[data-lesson-method="${method}"]`).click();
      assert.equal(await page.locator('#trainingAlgorithm').inputValue(),method);
      assert.equal(await page.locator(`[data-lesson-method="${method}"]`).getAttribute('aria-pressed'),'true');
      assert.equal(await page.locator('[data-lesson-method][aria-pressed="true"]').count(),1);
      assert.match(await page.locator('#methodLessonContent').textContent(),descriptions[method]);
      assert.equal(await page.locator('.method-diagram li').count(),3);
    }
    await page.locator('#trainingAlgorithm').selectOption('act');
    assert.equal(await page.locator('[data-lesson-method="act"]').getAttribute('aria-pressed'),'true');
    const colors=await page.locator('.workspace-card').evaluateAll(cards=>cards.map(c=>getComputedStyle(c).borderTopColor));
    assert.equal(new Set(colors).size,4,'Workspace colors must distinguish four stages');
    await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'outputs/dashboard/education-desktop.png'});
    await page.locator('#trainingConfiguration').screenshot({path:'outputs/dashboard/education-methods.png'});
    await page.locator('#evaluationWorkspace').screenshot({path:'outputs/dashboard/education-metrics.png'});
    await page.locator('#learningWorkspace').screenshot({path:'outputs/dashboard/education-agents.png'});
    for(const width of [1024,768,390,360]){
      await page.setViewportSize({width,height:844});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow at ${width}`);
      for(const id of ['trainingConfiguration','evaluationWorkspace','learningWorkspace']){
        await page.locator('#'+id).scrollIntoViewIfNeeded();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${id} overflow at ${width}`);
      }
      if(width===390){await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'outputs/dashboard/education-mobile.png'});await page.locator('#trainingConfiguration').screenshot({path:'outputs/dashboard/education-methods-mobile.png'});}
    }
    await page.locator('[data-view="examples"]').click();
    for(const name of ['LIBERO','LeIsaac / Isaac Lab','EnvHub · CartPole']){
      const card=page.locator('.example-card').filter({has:page.getByRole('heading',{name,exact:true})});
      await card.locator('.environment-guide summary').click();
      assert.match(await card.locator('.environment-guide').textContent(),/실행 환경 준비[\s\S]*서비스 연결 작업/);
    }
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Environment guide overflow');
    await page.screenshot({path:'outputs/dashboard/education-environments-mobile.png',fullPage:true});
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    console.log('Education: all four synchronized method diagrams, distinct stage colors, metric and role guides, responsive layout, no job submissions passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
