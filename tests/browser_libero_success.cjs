// Bundled measured LIBERO successes remain available without backend/trainer/provider.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
  await fs.mkdir('outputs/dashboard',{recursive:true});
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
    const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')writes.push(r.url());});
    await page.route('http://127.0.0.1:8787/**',route=>route.abort());
    await page.goto('http://127.0.0.1:3030');
    await page.locator('.libero-success-card').first().waitFor();
    const root=page.locator('#liberoSuccessGallery');
    assert.equal(await page.locator('.libero-success-card').count(),3);
    assert.match(await root.textContent(),/3 \/ 3/);
    assert.match(await root.textContent(),/추가 학습 없이/);
    const manifest=await page.request.get('http://127.0.0.1:3030/assets/success/libero-drawer/manifest.json').then(r=>r.json());
    assert.equal(manifest.successes,3);assert.equal(manifest.local_training,false);
    for(const [index,run] of manifest.runs.entries()){
      const card=page.locator('.libero-success-card').nth(index);
      assert.match(await card.textContent(),new RegExp(`최초 성공 ${run.first_success_step}스텝`));
      assert.match(await card.textContent(),/최종 성공 유지/);
      const video=card.locator('video');
      await video.evaluate(v=>new Promise((resolve,reject)=>{if(v.readyState>=2)return resolve();v.addEventListener('loadeddata',resolve,{once:true});v.addEventListener('error',reject,{once:true});v.load();}));
      assert.ok(Math.abs(await video.evaluate(v=>v.duration)-15.05)<0.05);
      await video.evaluate(async v=>{v.muted=true;await v.play();});
      await page.waitForFunction(i=>document.querySelectorAll('.libero-success-card video')[i].currentTime>0.1,index);
      await video.evaluate(v=>new Promise(resolve=>{v.pause();v.addEventListener('seeked',resolve,{once:true});v.currentTime=v.duration-0.1;}));
      assert.equal(await card.locator('a[download]').getAttribute('href'),'assets/success/libero-drawer/'+run.video);
    }
    await root.locator('summary').click();
    assert.equal(await root.locator('tbody tr').count(),3);
    for(const link of await root.locator('tbody a').all()){
      const response=await page.request.get('http://127.0.0.1:3030/'+await link.getAttribute('href'));
      assert.equal(response.status(),200);const trace=await response.json();assert.equal(trace.length,300);assert.equal(trace.at(-1).is_success,true);
    }
    await page.locator('#liberoSuccessShowcase').screenshot({path:'outputs/dashboard/libero-success-desktop.png'});
    for(const width of [1024,768,390,360]){
      await page.setViewportSize({width,height:844});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow at ${width}`);
      if(width===390)await page.locator('#liberoSuccessShowcase').screenshot({path:'outputs/dashboard/libero-success-mobile.png'});
    }
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    // Live catalog link is a navigation action only.
    await page.unroute('http://127.0.0.1:8787/**');await page.reload();
    await page.locator('[data-view="examples"]').click();
    const libero=page.locator('.example-card').filter({has:page.getByRole('heading',{name:'LIBERO',exact:true})});
    await libero.locator('summary').click();await libero.locator('.libero-gallery-link').click();
    assert.equal(await page.locator('#dashboardView').isVisible(),true);
    assert.equal(await page.locator('#liberoSuccessShowcase').isVisible(),true);
    assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);
    console.log('Actual LIBERO success gallery: all 3 native videos, measured outcomes, raw traces, offline playback, mobile layout and catalog navigation passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
