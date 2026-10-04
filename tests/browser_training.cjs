// Requires local servers and Playwright. Runs a real one-step ACT training job.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:3030');
    await page.locator('#connectionText').filter({hasText:'백엔드 연결됨'}).waitFor();
    await page.locator('[data-view="training"]').click();
    await page.locator('#trainingStart:enabled').waitFor();
    assert.equal(await page.locator('#simulationLaunch').isVisible(), false);
    await page.locator('#trainingDevice').selectOption('cpu');
    await page.locator('#trainingSteps').fill('1');
    await page.locator('#trainingBatch').fill('1');
    await page.locator('#trainingEpisodes').fill('1');
    await page.locator('#trainingStart').click();
    await page.locator('#trainingStop:visible').waitFor();
    assert.equal(await page.locator('#trainingStart').isDisabled(), true);
    await page.locator('#trainingStatus').filter({hasText:'학습 완료'}).waitFor({timeout:120000});
    assert.match(await page.locator('#trainingLogs').textContent(), /loss:/);
    assert.match(await page.locator('#trainingHistory').textContent(), /pretrained_model/);
    await page.screenshot({path:'outputs/dashboard/training-desktop.png',fullPage:true});
    // Exercise cancellation with a long job, then verify that starting unlocks.
    await page.locator('#trainingStart:enabled').waitFor();
    await page.locator('#trainingSteps').fill('100000');
    await page.locator('#trainingStart').click();
    await page.locator('#trainingStop:visible').waitFor();
    await page.locator('#trainingStop').click();
    await page.locator('#trainingStatus').filter({hasText:'학습 중지됨'}).waitFor({timeout:20000});
    await page.locator('#trainingStart:enabled').waitFor();
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path:'outputs/dashboard/training-mobile.png',fullPage:true});
    await page.reload();
    await page.locator('[data-view="training"]').click();
    await page.locator('#trainingHistory').filter({hasText:'체크포인트'}).waitFor();
    assert.deepEqual(errors, []);
    console.log('Training UI: real ACT checkpoint, logs, cancellation, history, mobile layout passed.');
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exitCode=1;});
