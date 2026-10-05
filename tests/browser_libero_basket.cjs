// Real bundled native outcomes; no trainer/provider/backend execution.
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
    await page.route('http://127.0.0.1:8787/**',r=>r.abort());
    await page.goto('http://127.0.0.1:3030/?libero=basket#liberoSuccessShowcase');
    const root=page.locator('#liberoSuccessGallery');
    await page.waitForFunction(()=>document.querySelector('#liberoSuccessGallery').dataset.task==='basket');
    assert.equal(await page.locator('.libero-success-card').count(),3);
    assert.match(await root.textContent(),/3 \/ 3/);
    assert.match(await root.textContent(),/20,000/);
    const manifest=await page.request.get('http://127.0.0.1:3030/assets/success/libero-basket/manifest.json').then(r=>r.json());
    assert.equal(manifest.successes,3);assert.equal(manifest.local_training,false);
    assert.equal(manifest.strict_weight_loading,true);
    for(const [index,run] of manifest.runs.entries()){
      const card=page.locator('.libero-success-card').nth(index);
      assert.match(await card.textContent(),new RegExp(`최초 성공 ${run.first_success_step}스텝`));
      const video=card.locator('video');
      await video.evaluate(v=>new Promise((resolve,reject)=>{if(v.readyState>=2)return resolve();v.addEventListener('loadeddata',resolve,{once:true});v.addEventListener('error',reject,{once:true});v.load();}));
      assert.ok(Math.abs(await video.evaluate(v=>v.duration)-20.05)<0.05);
      await video.evaluate(async v=>{v.muted=true;await v.play();});
      await page.waitForFunction(i=>document.querySelectorAll('.libero-success-card video')[i].currentTime>0.1,index);
      await video.evaluate(v=>new Promise(resolve=>{v.pause();v.addEventListener('seeked',resolve,{once:true});v.currentTime=v.duration-0.1;}));
      const trace=await page.request.get('http://127.0.0.1:3030/assets/success/libero-basket/'+run.trace).then(r=>r.json());
      assert.equal(trace.length,400);assert.equal(trace.at(-1).is_success,true);
      assert.equal(trace.findIndex(t=>t.is_success)+1,run.first_success_step);
    }
    await root.locator('summary').click();
    assert.match(await root.textContent(),/128×128/);assert.match(await root.textContent(),/뒤집지 않고/);
    assert.match(await root.textContent(),/temporal_ensemble_coeff=0.01/);
    await page.waitForTimeout(300);
    await page.locator('#liberoSuccessShowcase').screenshot({path:'outputs/dashboard/libero-basket-desktop.png'});
    await page.locator('[data-libero-case="drawer"]').click();
    assert.equal(await root.getAttribute('data-task'),'drawer');assert.match(await root.textContent(),/100,000/);
    assert.equal(await page.locator('.libero-success-card video source').first().getAttribute('src'),'assets/success/libero-drawer/episode-0-seed-1000.mp4');
    await page.locator('[data-libero-case="basket"]').click();
    assert.equal(await root.getAttribute('data-task'),'basket');
    assert.equal(await page.locator('[data-libero-case="basket"]').getAttribute('aria-pressed'),'true');
    for(const width of [1024,768,390,360]){
      await page.setViewportSize({width,height:844});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow at ${width}`);
      if(width===390)await page.locator('#liberoSuccessShowcase').screenshot({path:'outputs/dashboard/libero-basket-mobile.png'});
    }
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    console.log('Basket: all 3 native videos, exact successes/traces, task switching, offline playback and responsive layout passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
