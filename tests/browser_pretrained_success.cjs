// Read-only playback verification; supply a completed local report ID.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  assert.match(process.env.RX_SUCCESS_REPORT || '',/^[a-f0-9]{32}$/);
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`http://127.0.0.1:3030/?report=${process.env.RX_SUCCESS_REPORT}`);
    await page.locator('#videoNote').filter({hasText:'2/3 성공'}).waitFor();
    assert.equal(await page.locator('#reportSelect').inputValue(),process.env.RX_SUCCESS_REPORT);
    assert.equal(await page.locator('#videos video').count(),3);
    assert.equal(await page.locator('#resultKind').textContent(),'학습된 정책 실행');
    const data=await page.request.get(`http://127.0.0.1:8787/api/reports/${process.env.RX_SUCCESS_REPORT}`).then(r=>r.json());
    assert.equal(data.data.runs.filter(r=>r.success && r.final_success && r.max_reward===4).length,2);
    const video=page.locator('#videos video').first();
    await video.evaluate(v=>new Promise((resolve,reject)=>{
      if(v.readyState>=2)return resolve();
      v.addEventListener('loadeddata',resolve,{once:true});v.addEventListener('error',reject,{once:true});v.load();
    }));
    assert.ok(await video.evaluate(v=>v.duration>=8));
    await video.evaluate(v=>{v.currentTime=7.5;});
    await page.waitForTimeout(500);
    await page.screenshot({path:'outputs/dashboard/pretrained-success-desktop.png',fullPage:false});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:'outputs/dashboard/pretrained-success-mobile.png',fullPage:false});
    assert.deepEqual(errors,[]);
    console.log('Pretrained ACT success report, full video playback and desktop/mobile UI passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
