import {environmentGuides} from './education.js';
import {connectAgents} from './hermes.js';
import {connectTraining} from './training.js';
import {connectPlatform} from './platform.js';
import {loadShowcase} from './showcase.js';
loadShowcase();
const API = new URLSearchParams(location.search).get('api') || 'http://127.0.0.1:8787';
const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = value => Number(value).toFixed(3);
const diagnosis = {no_contact:'접촉 없음',orientation_mismatch:'각도 불일치',position_mismatch:'위치 불일치',insufficient_overlap:'정렬 미세 오차'};
let report, reportId, traces = {}, index = 0, playing = false, lastTick = 0, generation = 0, currentJob, jobFinished, pollBusy = false, observedRunningJob;
const agents = connectAgents({api, mediaUrl:path=>API+path, reportId:()=>reportId, reportKind:()=>report?.kind, error, simulationRunning:()=>currentJob?.status==='running'||training.isRunning()});
const training = connectTraining({api, mediaUrl:path=>API+path, error, busy:()=>currentJob?.status==='running'||agents.isRunning()});

async function api(path, options) {
  const response = await fetch(API + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `요청 실패 (${response.status})`);
  return data;
}
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function connected(ok) {
  $('connectionText').textContent = ok ? '백엔드 연결됨' : '백엔드 연결 대기';
  $('connectionDot').className = `tiny-dot ${ok ? '' : 'offline'}`;
}
function view(name) {
  $('dashboardView').hidden = name !== 'dashboard'; $('examplesView').hidden = name !== 'examples';
  $('trainingView').hidden = name !== 'training'; $('simulationLaunch').hidden = name === 'training';
  document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === name));
  $('breadcrumb').textContent = name === 'dashboard' ? '플랫폼 홈' : '환경 라이브러리';
  $('pageTitle').textContent = name === 'dashboard' ? '로봇 학습과 Agent, 하나의 플랫폼.' : '다음 해법을 위한 실행 환경.';
  $('pageSubtitle').textContent = name === 'dashboard' ? '정책을 학습하고, 시뮬레이션으로 검증하고, Agent와 다음 해법을 찾으세요.' : '지금 실행할 수 있는 환경부터, 다음에 연결할 벤치마크까지.';
  if (name === 'training') {
    $('breadcrumb').textContent = '학습 & Agents'; $('pageTitle').textContent = '학습에서 검증까지, 해법을 만드는 곳.';
    $('pageSubtitle').textContent = '로봇 정책 학습, Agent 실험 설계, 시뮬레이터 평가를 하나의 흐름으로 연결합니다.';
  }
  playing = false; updatePlay();
}
document.querySelectorAll('[data-view]').forEach(button => button.onclick = () => view(button.dataset.view));
connectPlatform({view});

async function loadReports(preferred) {
  const items = await api('/api/reports');
  $('reportSelect').innerHTML = items.map(item => `<option value="${esc(item.id)}">${esc(item.title)}</option>`).join('');
  $('empty').hidden = items.length > 0;
  if (!items.length) return;
  const selected = items.find(item => item.id === preferred) || items.find(item => item.id === reportId)
    || items.find(item => item.id === 'agent') || items[0];
  $('reportSelect').value = selected.id;
  await loadReport(selected.id);
}
async function loadReport(id) {
  const token = ++generation;
  playing = false; updatePlay(); traces = {}; reportId = id;
  const result = await api(`/api/reports/${id}`);
  if (token !== generation) return;
  report = result;
  agents.refresh();
  $('agentView').hidden = result.kind !== 'agent';
  $('videoPanel').hidden = !result.media.length;
  $('resultKind').textContent = result.kind === 'agent' ? result.data.mode === 'quick smoke' ? '빠른 확인' : '독립 평가' : '동작 확인';
  const recordingName = name => {
    const run = result.data.method === 'pretrained ACT' && result.data.runs.find(run=>run.name===name);
    return run ? `Cube transfer · Seed ${run.seed} · ${run.success?'성공':'실패'}` : {baseline:'기존 원형 동작',planner:'상태 기반 계획 제어',aloha:'ALOHA · Peg insertion',transfer:'ALOHA · Cube transfer',pusht:'PushT · 원형 동작'}[name] || name;
  };
  $('videos').innerHTML = result.media.map(media => `<article><h3>${esc(recordingName(media.name))}</h3><video controls preload="auto" ${media.poster ? `poster="${esc(API + media.poster)}"` : ''} src="${esc(API + media.url)}"></video></article>`).join('');
  $('demoSummary').textContent = '';
  if (result.kind === 'demo') {
    if (result.data.method === 'pretrained ACT') {
      $('resultKind').textContent = '학습된 정책 실행';
      $('resultDescription').textContent = '공개 사전학습 ACT 모델이 MuJoCo에서 큐브를 집어 다른 팔에 전달하는 실행입니다.';
      $('videoNote').textContent = `${result.data.runs.filter(run=>run.success).length}/${result.data.runs.length} 성공 · 공식 성공 기준: 보상 4 · 실패 실행도 포함`;
      $('demoSummary').textContent = result.data.runs.map(run=>`Seed ${run.seed} · ${run.success?'성공':'실패'} · 최고 보상 ${run.max_reward} · ${run.steps}스텝`).join(' / ');
      return;
    }
    $('resultDescription').textContent = '학습 전 정해진 관절 동작으로 시뮬레이터의 작동을 확인한 기록입니다.';
    $('videoNote').textContent = '관절 동작 데모 · 학습된 정책 없음';
    $('demoSummary').textContent = result.data.runs.map(run => `${run.environment} · ${run.steps}스텝`).join(' / ');
    return;
  }
  const data = result.data, baseline = data.baseline.summary, planner = data.planner.summary;
  $('resultDescription').textContent = `${planner.episodes}개 같은 초기 조건 · 최대 ${data.step_limit}스텝 · 상태 기반 제어 / 알려진 물리 모델`;
  $('successRate').textContent = `${Math.round(planner.success_rate * 100)}%`;
  $('successDetail').textContent = `${data.planner.runs.filter(run => run.success).length} / ${planner.episodes} 성공 · 기존 ${Math.round(baseline.success_rate * 100)}%`;
  $('successBar').style.width = `${planner.success_rate * 100}%`;
  $('bestReward').textContent = fmt(planner.mean_best_reward);
  $('bestDetail').textContent = `기존 ${fmt(baseline.mean_best_reward)} → 계획 ${fmt(planner.mean_best_reward)}`;
  $('finalReward').textContent = fmt(planner.mean_final_reward);
  $('finalDetail').textContent = `기존 ${fmt(baseline.mean_final_reward)} → 계획 ${fmt(planner.mean_final_reward)}`;
  $('wallTime').textContent = `${Number(planner.mean_wall_seconds).toFixed(2)}s`;
  $('wallDetail').textContent = `에피소드당 · ${planner.mean_steps.toFixed(1)}스텝`;
  $('seed').innerHTML = data.seed_split.test.map(seed => `<option value="${seed}">Seed ${seed}</option>`).join('');
  $('episodeRows').innerHTML = data.planner.runs.map((run, i) => `<tr data-seed="${run.seed}" tabindex="0" aria-label="Seed ${run.seed} 재생"><td>Seed ${run.seed}</td><td>${fmt(data.baseline.runs[i].best_reward)}</td><td>${fmt(run.best_reward)}</td><td><span class="badge ${run.success ? 'success' : ''}">${run.success ? '성공' : '미완료'}</span></td><td>${run.steps}</td><td>${run.success ? '목표 달성' : diagnosis[run.failure] || esc(run.failure)}</td></tr>`).join('');
  $('episodeRows').querySelectorAll('tr').forEach(row => {
    const select = () => { $('seed').value = row.dataset.seed; loadTrace(Number(row.dataset.seed)).catch(e => error(e.message)); };
    row.onclick = select;
    row.onkeydown = event => { if (event.key === 'Enter') select(); };
  });
  $('method').innerHTML = `<p>설정 탐색: ${data.seed_split.tuning.join(', ')} · 검증: ${data.seed_split.validation.join(', ')} · 독립 평가: ${data.seed_split.test.join(', ')}</p><p>성공은 환경의 공식 종료 조건입니다. 단계별 보상은 목표 영역과 물체의 겹침 정도에 따라 계산됩니다. 학습된 신경망이나 실시간 LLM 호출은 사용하지 않았습니다.</p><code>${esc(JSON.stringify(data.selected_settings))}</code><p><a href="${esc(API + `/api/reports/${id}`)}" target="_blank" rel="noreferrer">실험 데이터 JSON ↗</a></p>`;
  $('videoNote').textContent = `Seed ${data.seed_split.test[0]} · 다른 초기 조건은 위의 상태 재생으로 확인`;
  await loadTrace(data.seed_split.test[0]);
}
async function loadTrace(seed) {
  const token = ++generation, id = reportId;
  playing = false; updatePlay(); $('play').disabled = true;
  $('replayNote').textContent = '상태 기록 불러오는 중…';
  try {
    const [baseline, planner] = await Promise.all(['baseline','planner'].map(name => api(`/api/reports/${id}/traces/${name}/${seed}`)));
    if (token !== generation) return;
    traces = {baseline, planner}; index = 0;
    $('timeline').max = Math.max(baseline.length, planner.length) - 1;
    for (const name of ['baseline','planner']) {
      const run = report.data[name].runs.find(run => run.seed === seed);
      $(`${name}Badge`).textContent = run.success ? '목표 달성' : '미완료';
      $(`${name}Badge`).className = `badge ${run.success ? 'success' : ''}`;
    }
    $('episodeRows').querySelectorAll('tr').forEach(row => row.classList.toggle('selected', Number(row.dataset.seed) === seed));
    $('replayNote').textContent = '실제 기록된 상태 재생 · 새로운 물리 계산 없음';
    $('play').disabled = false; render();
  } catch (e) { error(e.message); $('replayNote').textContent = '이 초기 조건의 상태 기록을 불러올 수 없습니다.'; }
}
function drawT(ctx, pose, fill, stroke) {
  ctx.save(); ctx.translate(pose[0], pose[1]); ctx.rotate(pose[2]);
  ctx.beginPath(); ctx.moveTo(-60,0); ctx.lineTo(60,0); ctx.lineTo(60,30); ctx.lineTo(15,30);
  ctx.lineTo(15,120); ctx.lineTo(-15,120); ctx.lineTo(-15,30); ctx.lineTo(-60,30); ctx.closePath();
  ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = stroke; ctx.lineWidth = 1.5; ctx.stroke(); ctx.restore();
}
function board(name, color) {
  const canvas = $(`${name}Canvas`), ctx = canvas.getContext('2d'), trace = traces[name];
  const current = trace[Math.min(index, trace.length - 1)], state = current.state;
  ctx.clearRect(0,0,512,512); ctx.fillStyle = '#fcfdfb'; ctx.fillRect(0,0,512,512);
  ctx.strokeStyle = '#edf1eb'; ctx.lineWidth = 1;
  for(let i=32;i<512;i+=32) {ctx.beginPath();ctx.moveTo(i,0);ctx.lineTo(i,512);ctx.stroke();ctx.beginPath();ctx.moveTo(0,i);ctx.lineTo(512,i);ctx.stroke();}
  ctx.strokeStyle = '#dce5dc'; ctx.strokeRect(5,5,501,501);
  drawT(ctx,[256,256,Math.PI/4],'#e0eee0','#a3c9ab');
  ctx.beginPath(); trace.slice(0,Math.min(index + 1,trace.length)).forEach((item,i)=>i ? ctx.lineTo(item.state[0],item.state[1]) : ctx.moveTo(item.state[0],item.state[1]));
  ctx.strokeStyle = name === 'planner' ? '#157a6933' : '#d8963633'; ctx.lineWidth = 2; ctx.stroke();
  drawT(ctx,state.slice(2),name === 'planner' ? '#64998e' : '#bca077',name === 'planner' ? '#3e776b' : '#987a52');
  ctx.setLineDash([4,5]);ctx.beginPath();ctx.moveTo(state[0],state[1]);ctx.lineTo(...current.action);ctx.strokeStyle=color;ctx.lineWidth=1.4;ctx.stroke();ctx.setLineDash([]);
  ctx.beginPath();ctx.arc(current.action[0],current.action[1],4,0,Math.PI*2);ctx.strokeStyle=color;ctx.stroke();
  ctx.beginPath();ctx.arc(state[0],state[1],15,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=3;ctx.stroke();
  ctx.fillStyle='#8aa08d';ctx.font='10px system-ui';ctx.fillText('TARGET',218,215);
  $(`${name}Current`).textContent = fmt(current.reward);
  $(`${name}Step`).textContent = index >= trace.length ? `종료 · ${trace.length}스텝` : `${index + 1} / ${trace.length}스텝`;
}
function chart() {
  const canvas = $('rewardChart'), ctx = canvas.getContext('2d'), w=1000,h=190,left=42,right=16,top=12,bottom=30;
  ctx.clearRect(0,0,w,h); const max = Number($('timeline').max), range = w-left-right;
  ctx.font='11px system-ui'; ctx.fillStyle='#8b9990';ctx.strokeStyle='#edf1eb';ctx.lineWidth=1;
  for (const value of [0,.5,1]) {const y=top+(1-value)*(h-top-bottom);ctx.fillText(value.toFixed(1),5,y+4);ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right,y);ctx.stroke();}
  for (const [name,color] of [['baseline','#d89636'],['planner','#157a69']]) {
    ctx.beginPath();traces[name].forEach((t,i)=>{const x=left+i/max*range,y=top+(1-t.reward)*(h-top-bottom); i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.strokeStyle=color;ctx.lineWidth=2;ctx.stroke();
  }
  ctx.fillStyle='#8b9990';for(const value of [0,Math.round(max/2),max])ctx.fillText(String(value+1),left+value/max*range-5,h-10);
  const x=left+index/max*range;ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,h-bottom);ctx.strokeStyle='#8eb5a3';ctx.setLineDash([3,4]);ctx.lineWidth=1;ctx.stroke();ctx.setLineDash([]);
}
function render() {
  if (!traces.baseline?.length) return;
  $('timeline').value = index; $('stepLabel').textContent = `STEP ${String(index+1).padStart(3,'0')} / ${Number($('timeline').max)+1}`;
  board('baseline','#d89636'); board('planner','#157a69'); chart();
}
function updatePlay() { $('play').textContent = playing ? 'Ⅱ' : '▶'; $('play').setAttribute('aria-label',playing ? '일시 정지':'재생'); }
$('play').onclick = () => { if (!traces.baseline?.length) return; if(index>=Number($('timeline').max))index=0;playing=!playing;lastTick=0;updatePlay();render(); };
$('timeline').oninput = () => {index=Number($('timeline').value);playing=false;updatePlay();render();};
$('seed').onchange = () => loadTrace(Number($('seed').value));
$('reportSelect').onchange = () => loadReport($('reportSelect').value).catch(e=>error(e.message));
function animate(time) {
  if(playing && time-lastTick >= 100/Number($('speed').value)) {lastTick=time;index=Math.min(index+1,Number($('timeline').max));render();if(index===Number($('timeline').max)){playing=false;updatePlay();}}
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);

async function loadExamples() {
  const data = await api('/api/examples');
  const symbols = {push:'⊥',arms:'⋈',cube:'◇',world:'◎',layers:'▱',robot:'⌘',hub:'⌁'};
  $('examples').innerHTML = data.examples.map(example => `<article class="example-card"><div class="example-art"><span class="example-symbol">${symbols[example.icon]}</span><span class="badge ${example.available?'success':''}">${esc(example.status)}</span></div><p class="eyebrow">${esc(example.category)}</p><h3>${esc(example.name)}</h3><p>${esc(example.description)}</p><span class="example-requirement">${esc(example.requirements)}</span>${environmentGuides[example.id]?`<details class="environment-guide"><summary>어떤 준비와 연결이 필요한가요?</summary><strong>실행 환경 준비</strong><p>${esc(environmentGuides[example.id].setup)}</p><strong>서비스 연결 작업</strong><p>${esc(environmentGuides[example.id].connection)}</p><small>현재는 공식 예제 안내입니다. 이 서비스의 실행 버튼은 아직 제공하지 않습니다.</small></details>`:''}<div class="example-actions"><a href="${esc(example.source)}" target="_blank" rel="noreferrer">공식 가이드 ↗</a>${example.available?`<button data-example="${esc(example.id)}">실험 선택 →</button>`:`<span class="muted">${esc(environmentGuides[example.id]?.label || '실행기 연결 필요')}</span>`}</div></article>`).join('');
  $('examples').querySelectorAll('[data-example]').forEach(button=>button.onclick=()=>{$('experiment').value=button.dataset.example;configureExperiment();view('dashboard');$('simulationLaunch').scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});$('experiment').focus({preventScroll:true});});
}
function configureExperiment() {const agent=$('experiment').value==='pusht-agent';$('mode').disabled=!agent;$('steps').value=agent?300:250;}
$('experiment').onchange = configureExperiment;
$('run').onclick = async () => {
  error('');$('run').disabled=true;
  try {currentJob=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({example:$('experiment').value,steps:Number($('steps').value),quick:$('mode').value==='quick'})});jobFinished=null;await poll();}
  catch(e){error(e.message);$('run').disabled=false;}
};
async function poll() {
  if(pollBusy)return;pollBusy=true;
  try {
    const state=await api('/api/jobs/current');connected(true);currentJob=state;
    await training.refresh();
    $('run').disabled=state.status==='running'||agents.isRunning()||training.isRunning();$('run').textContent=state.status==='running'?'실험 실행 중…':'실험 실행 →';
    agents.refresh();
    $('jobPanel').hidden=state.status==='idle';
    if(state.status!=='idle') {
      $('jobTitle').textContent=state.title;$('jobStatus').textContent={running:'실행 중 · 화면을 계속 탐색할 수 있습니다',completed:'완료',failed:'실행 실패'}[state.status];
      $('jobLogs').textContent=(state.logs||[]).join('\n');$('jobDot').className=`tiny-dot ${state.status==='running'?'waiting':state.status==='failed'?'offline':''}`;
      if(state.status==='running')observedRunningJob=state.id;
      if(state.status==='completed' && jobFinished!==state.id){jobFinished=state.id;if(observedRunningJob===state.id)await loadReports(state.id);}
      if(state.status==='failed' && jobFinished!==state.id){jobFinished=state.id;error('실험 실행에 실패했습니다. 실행 로그에서 원인을 확인해 주세요.');}
    }
  } catch(e) {connected(false);$('run').disabled=true;}
  finally {pollBusy=false;}
}
async function boot() {
  $('run').disabled=true;
  try {await api('/api/health');connected(true);error('');await Promise.all([loadReports(new URLSearchParams(location.search).get('report')),loadExamples()]);await poll();setInterval(poll,2000);}
  catch(e){connected(false);error('백엔드에 연결할 수 없습니다. sh run_app.sh 실행 상태를 확인해 주세요.');setTimeout(boot,5000);}
}
boot();
