// Read-only UI audit of the actual persisted Hermes experiment. No fake results.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1100}});
  const errors = [], leaked = [];
  page.on('pageerror', error=>errors.push(error.message));
  page.on('request',request=>{if(request.url().includes(':8700')||request.url().includes(':8679')||request.headers().authorization)leaked.push(request.url());});
  await page.goto('http://127.0.0.1:3030');
  await page.locator('#hermesConnection').filter({hasText:'rx-dev 연결됨'}).waitFor({timeout:30000});
  await page.locator('#agentResults .agent-result').first().waitFor();
  const status = await (await page.request.get('http://127.0.0.1:8787/api/agents/current')).json();
  console.log(JSON.stringify({id:status.id,status:status.status,stage:status.stage,roles:Object.keys(status.roles||{})}));
  if (process.env.EXPECT_COMPLETED === '1') {
    assert.equal(status.status,'completed');
    await page.locator('#agentProgress').filter({hasText:'완료'}).waitFor();
    assert.equal(await page.locator('#agentResults .agent-result').count(),status.recordings ? 5 : 4);
    assert.equal(await page.locator('#agentRun').isEnabled(),true);
    if(status.evaluation.success_intervals_95) await page.locator('.agent-uncertainty').filter({hasText:'95% Wilson'}).waitFor();
  }
  if(process.env.EXPECT_STUDY === '1') {
    const study=await (await page.request.get('http://127.0.0.1:8787/api/controller-study')).json();
    assert.equal(study.test.trials.length,2);
    await page.locator('#controllerStudy').waitFor();
    for(const trial of study.test.trials) assert.equal(trial.runs.length,30);
    assert.ok((await page.locator('#controllerStudy').innerText()).includes(`${study.test.trials[1].runs.filter(r=>r.success).length} / 30`));
  }
  await page.screenshot({path:'outputs/dashboard/hermes-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'outputs/dashboard/hermes-mobile.png',fullPage:true});
  const width = await page.evaluate(()=>({viewport:innerWidth,body:document.body.scrollWidth}));
  assert.ok(width.body<=width.viewport,`Mobile overflow: ${JSON.stringify(width)}`);
  assert.deepEqual(errors,[]); assert.deepEqual(leaked,[]);
  await browser.close();
  console.log('PASS: live rx-dev connection, persisted agent results, desktop/mobile, no JS errors, no gateway credentials or direct browser calls');
})().catch(error=>{console.error(error);process.exit(1);});
