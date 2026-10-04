// Real UI learning/evaluation checks. Requires the local app and Playwright.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:3030');
    await page.locator('[data-view="training"]').click();
    await page.locator('#trainingStart:enabled').waitFor();
    const environment=process.env.RX_TRAIN_ENV || 'pusht';
    await page.locator('#trainingEnvironment').selectOption(environment);
    for (const algorithm of ['act','diffusion','ppo','sac']) {
      await page.locator('#trainingMode').selectOption('new');
      await page.locator('#trainingAlgorithm').selectOption(algorithm);
      const imitation = ['act','diffusion'].includes(algorithm);
      assert.equal(await page.locator('#trainingDataset').isEnabled(), imitation);
      await page.locator('#trainingSteps').fill(imitation ? '1' : algorithm==='ppo' ? '128' : '64');
      await page.locator('#trainingBatch').fill(imitation ? '1' : '8');
      if (imitation) await page.locator('#trainingEpisodes').fill('1');
      const launched = page.waitForResponse(response=>response.url().endsWith('/api/training') && response.request().method()==='POST');
      await page.locator('#trainingStart').click();
      const response = await launched;
      assert.equal(response.status(), 202);
      const job = await response.json();
      assert.equal(job.policy, algorithm);
      assert.equal(job.config.environment,environment);
      await page.locator('#trainingStatus').filter({hasText:'학습 완료'}).waitFor({timeout:180000});
      // Evaluate the exact new checkpoint, rather than a different historical model.
      await page.locator('#policyEvalEpisodes').fill('1');
      await page.locator('#policyEvalSteps').fill('10');
      const evaluation = page.waitForResponse(response=>response.url().endsWith('/api/training/evaluate') && response.request().method()==='POST');
      await page.locator(`[data-policy-eval="${job.id}"]`).click();
      const evalResponse = await evaluation;
      assert.equal(evalResponse.status(),202);
      const evaluated = await evalResponse.json();
      assert.equal(evaluated.config.source_job, job.id);
      assert.equal(evaluated.config.environment,environment);
      await page.locator('#trainingStatus').filter({hasText:'정책 평가 완료'}).waitFor({timeout:180000});
      const record = page.locator('.training-record').filter({has:page.locator('small').filter({hasText:evaluated.id})});
      await record.locator('summary').filter({hasText:'평가 영상'}).click();
      await record.locator('video').evaluate(video=>new Promise((resolve,reject)=>{
        if(video.readyState>=2)return resolve();
        video.addEventListener('loadeddata',resolve,{once:true});
        video.addEventListener('error',()=>reject(new Error('Video decoding failed')),{once:true});
        video.load();
      }));
      assert.equal(await page.locator('#policyEvaluations').textContent().then(text=>text.includes(algorithm==='diffusion'?'Diffusion Policy':algorithm.toUpperCase())), true);
      // Ensure polling does not replace the playing video node.
      await record.locator('video').evaluate(video=>video.dataset.testMarker='keep');
      await page.waitForTimeout(2300);
      assert.equal(await record.locator('video').getAttribute('data-test-marker'),'keep');
    }
    await page.locator('#trainingAlgorithm').selectOption('act');
    await page.locator('#trainingMode').selectOption('resume');
    assert.equal(await page.locator('#trainingDataset').isDisabled(),true);
    assert.equal(await page.locator('#trainingBatch').isDisabled(),true);
    await page.locator('#trainingSteps').fill('2');
    await page.locator('#trainingStart').click();
    await page.locator('#trainingStop:visible').waitFor();
    await page.locator('#trainingStatus').filter({hasText:'학습 완료'}).waitFor({timeout:180000});
    await page.screenshot({path:`outputs/dashboard/training-methods-${environment}-desktop.png`,fullPage:false});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:`outputs/dashboard/training-methods-${environment}-mobile.png`,fullPage:false});
    assert.deepEqual(errors,[]);
    console.log('Four learning methods, actual checkpoints, seeded evaluations, video decoding, resume and mobile UI passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
