// Bundled playback works without a simulation backend or local outputs.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    if(!process.env.RX_SHOWCASE_LIVE) await page.route('http://127.0.0.1:8787/**',route=>route.abort());
    await page.goto('http://127.0.0.1:3030');
    await page.locator('.success-card').first().waitFor();
    assert.equal(await page.locator('.success-card').count(),2);
    assert.match(await page.locator('#successGallery').textContent(),/2\/3 성공/);
    const video=page.locator('.success-card video').first();
    await video.evaluate(v=>new Promise((resolve,reject)=>{
      if(v.readyState>=2)return resolve();
      v.addEventListener('loadeddata',resolve,{once:true});v.addEventListener('error',reject,{once:true});v.load();
    }));
    assert.ok(await video.evaluate(v=>v.duration>=8));
    await video.evaluate(async v=>{v.muted=true;await v.play();});
    await page.waitForFunction(()=>document.querySelector('.success-card video').currentTime>0.2);
    await video.evaluate(v=>v.pause());
    await page.screenshot({path:'outputs/dashboard/showcase-desktop.png',fullPage:false});
    await page.locator('.success-evidence summary').click();
    assert.equal(await page.locator('.success-evidence tbody tr').count(),3);
    assert.equal(await page.locator('.success-failure video').count(),1);
    assert.equal(await page.locator('.success-caption a').first().getAttribute('download'),'');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.locator('#successShowcase').scrollIntoViewIfNeeded();
    await page.screenshot({path:'outputs/dashboard/showcase-mobile.png',fullPage:false});
    assert.deepEqual(errors,[]);
    console.log(`Bundled success videos ${process.env.RX_SHOWCASE_LIVE?'with live app':'without backend'}: full evidence, failure video, downloads and mobile layout passed.`);
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
