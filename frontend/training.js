import {renderMethodLesson} from './education.js';
import {statusBadge,successCard} from './learning_cards.js';
import {connectLearningAgents} from './learning_agents.js';
import {environments,environmentOf,canEvaluate} from './learning_environments.js';
export function connectTraining({api, mediaUrl, error, busy}) {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const statuses = {idle:'학습 대기',running:'실행 중 · 준비 시간 포함',stopping:'중지 중',stopped:'학습 중지됨',completed:'학습 완료 · 체크포인트 저장됨',failed:'실행 실패 · 로그를 확인하세요',interrupted:'서버 재시작으로 중단됨'};
  const names = {act:'ACT',diffusion:'Diffusion Policy',ppo:'PPO',sac:'SAC'};
  let state = {status:'idle'}, submitting = false, history = [], methods = [], historyRendered = '', sourceRendered = '', visibleRecords=6, evaluationsRendered='';
  const rl = () => ['ppo','sac'].includes($('trainingAlgorithm').value);
  const ownRunning = () => submitting || ['running','stopping'].includes(state.status);
  const learning = connectLearningAgents({api,error,getHistory:()=>history,device:()=>$('trainingDevice').value,busy:()=>ownRunning() || busy(),onChange:controls});
  const isRunning = () => ownRunning() || learning.isRunning();
  const eligible = () => history.filter(job => job.kind !== 'evaluation' && environmentOf(job.config) === $('trainingEnvironment').value && job.policy === $('trainingAlgorithm').value && job.checkpoints.length && !['running','stopping'].includes(job.status));
  function controls() {
    const blocked = isRunning() || busy();
    document.querySelectorAll("[data-lesson-method]").forEach(button=>button.disabled=blocked);
    $('trainingStart').disabled = blocked || ($('trainingMode').value !== 'new' && !$('trainingSource').value);
    $('trainingStop').hidden = !['running','stopping'].includes(state.status) || learning.isRunning();
    $('trainingStop').disabled = state.status === 'stopping';
    document.querySelectorAll('[data-policy-eval]').forEach(button => button.disabled = blocked);
  }
  function sources() {
    const jobs = eligible();
    const signature = JSON.stringify(jobs.map(job => [job.id,job.status]));
    if (sourceRendered === signature) return false;
    sourceRendered = signature;
    const selected = $('trainingSource').value;
    $('trainingSource').innerHTML = jobs.map(job => `<option value="${job.id}">${names[job.policy]} · ${esc(new Date(job.started_at*1000).toLocaleString())} · ${job.id.slice(0,8)}</option>`).join('');
    if (jobs.some(job => job.id === selected)) $('trainingSource').value = selected;
    return selected !== $('trainingSource').value;
  }
  function configure(loadSource=false) {
    const algorithm = $('trainingAlgorithm').value;
    const environment=environments[$('trainingEnvironment').value];
    $('trainingMode').querySelector('[value="finetune"]').disabled = rl();
    if (rl() && $('trainingMode').value === 'finetune') $('trainingMode').value = 'new';
    const mode = $('trainingMode').value;
    document.querySelectorAll('[data-imitation]').forEach(label => label.hidden = rl());
    document.querySelectorAll('[data-rl]').forEach(label => label.hidden = !rl());
    $('trainingRolloutLabel').hidden = algorithm !== 'ppo';
    $('trainingSourceLabel').hidden = mode === 'new';
    const changedSource = sources();
    const source = history.find(job => job.id === $('trainingSource').value);
    if (source && mode !== 'new' && !rl()) $('trainingPreset').value = source.config.preset || 'standard';
    if ((loadSource || changedSource) && source && mode === 'resume') {
      $('trainingBatch').value = source.config.batch_size;
      $('trainingSeed').value = source.config.seed;
      if (!rl()) {
        $('trainingDataset').value = source.config.dataset;
        $('trainingEpisodes').value = source.config.episodes;
        $('trainingSteps').value = Math.min(100000, source.config.steps + 1000);
      } else {
        $('trainingLearningRate').value = source.config.learning_rate;
        $('trainingGamma').value = source.config.gamma;
        $('trainingRollout').value = source.config.rollout_steps;
      }
    }
    for (const id of ['trainingDataset','trainingEpisodes']) $(id).disabled = rl() || mode === 'resume';
    for (const id of ['trainingBatch','trainingSeed','trainingLearningRate','trainingGamma','trainingRollout']) $(id).disabled = mode === 'resume';
    $('trainingPreset').disabled = mode !== 'new';
    $('trainingSteps').min = rl() ? '32' : '1';
    $('trainingSteps').max = rl() ? '1000000' : '100000';
    $('trainingBatch').min = rl() ? '2' : '1';
    if (rl() && mode === 'new' && Number($('trainingBatch').value) < 2) $('trainingBatch').value = 8;
    $('trainingStepLabel').textContent = rl() ? '수집할 환경 스텝 · 이어 학습은 추가량' : mode === 'resume' ? '재개 후 총 학습 스텝 목표' : '학습 업데이트 스텝';
    $('trainingStart').textContent = `${names[algorithm]} ${mode === 'finetune' ? '미세조정' : mode === 'resume' ? '이어 학습' : '학습 시작'} →`;
    renderMethodLesson(algorithm,ownRunning() || busy() || learning.isRunning());
    const method = methods.find(item => item.id === algorithm);
    $('trainingMethodInfo').textContent = method ? `${environment.name} · ${method.description} 입력: ${rl()?environment.input:method.input} · ${method.engine}` : '';
    $('trainingNotes').textContent = rl() ? `${environment.name}에서 경험을 직접 수집합니다. ${environment.input}를 입력으로 받고, 환경의 기본 보상을 사용합니다. 영상 모델과 입력 조건이 다릅니다. PPO 스텝은 경험 수집 간격의 배수여야 합니다. 모델과 로그는 로컬에 저장됩니다.` : '처음 N개 시연 에피소드를 사용합니다. 작은 모델은 로컬 실험용으로 구조를 줄인 설정입니다. 미세조정은 가중치를 가져와 새 optimizer로 학습하고, 재개는 optimizer와 스텝을 복원합니다. 데이터셋과 영상 인코더 초기 가중치를 다운로드하며 결과는 로컬에 저장됩니다.';
    $('learningSignalInfo').textContent=rl()?'환경 경험과 보상으로 정책을 학습합니다.':'시연 데이터로 행동을 학습합니다.';
    $('experienceSignal').hidden=!rl();
    $('trainingConfigSummary').textContent=`${names[algorithm]} · ${environment.name} · ${$('trainingDevice').value.toUpperCase()}`;
    controls();
  }
  function renderHistory() {
    const filter=$('trainingHistoryFilter').value;
    const query=$('trainingHistorySearch').value.trim().toLowerCase();
    const signature=JSON.stringify([history.map(({logs,...job})=>job),filter,query,visibleRecords]);
    if(signature===historyRendered)return;
    historyRendered=signature;
    const matched=history.filter(job=>(filter==='all' || (job.kind==='evaluation'?'evaluation':'training')===filter) &&
      (!query || [job.id,job.config.source_job,job.policy,names[job.policy],environments[environmentOf(job.config)].name].join(' ').toLowerCase().includes(query)));
    const visible=matched.slice(0,visibleRecords);
    $('trainingHistoryCount').textContent=`${visible.length} / ${matched.length} 기록`;
    $('trainingHistoryMore').hidden=visible.length>=matched.length;
    $('trainingHistory').innerHTML=visible.length?visible.map(job=>{
      const evaluation=job.kind==='evaluation', config=job.config;
      const environment=environments[environmentOf(config)];
      const saved=!evaluation && job.checkpoints.length && !['running','stopping'].includes(job.status);
      const label=evaluation?'정책 평가':{new:'새 학습',finetune:'미세조정',resume:'이어 학습'}[config.mode] || '학습';
      return `<article class="training-record history-record-card" data-record-id="${esc(job.id)}"><div class="record-card-heading"><div><span class="record-kind">${esc(label)}</span><h3>${esc(names[job.policy] || job.policy)} <span>· ${esc(environment.name)}</span></h3></div>${statusBadge(job.status,evaluation && job.status==='completed'?'평가 완료':statuses[job.status] || job.status)}</div>
        <div class="record-metrics"><div><span>${evaluation?'평가 에피소드':'설정 스텝'}</span><strong>${Number(evaluation?config.episodes:config.steps).toLocaleString()}</strong></div><div><span>${evaluation?'최대 실행 스텝':'연산 장치'}</span><strong>${evaluation?config.step_limit:esc(config.device.toUpperCase())}</strong></div><div><span>${job.evaluation?'성공률':evaluation?'평가 결과':'체크포인트'}</span><strong>${job.evaluation?(job.evaluation.success_rate*100).toFixed(1)+'%':evaluation?'미측정':job.checkpoints.length?'저장됨':'없음'}</strong></div></div>
        <small class="record-date">${esc(new Date(job.started_at*1000).toLocaleString())}</small><small class="record-id">${esc(job.id)}</small>
        ${saved && canEvaluate(config)?`<div class="training-actions"><button class="primary" data-policy-eval="${job.id}">이 정책 평가 →</button></div>`:''}
        ${job.videos?.length?`<details><summary>평가 영상 ${job.videos.length}개</summary><div class="record-videos">${job.videos.map(path=>`<video controls playsinline preload="none" src="${esc(mediaUrl(path))}"></video>`).join('')}</div></details>`:''}
        <details><summary>설정과 체크포인트</summary><p>${esc(config.dataset || environment.input)} · Seed ${config.seed}</p>${config.source_job?`<p>원본 학습 <code>${esc(config.source_job)}</code></p>`:''}${job.checkpoints.map(path=>`<p><code>${esc(path)}</code></p>`).join('')}${job.evaluation?`<p>최고 보상 평균 ${job.evaluation.mean_best_reward.toFixed(3)} · Seed ${job.evaluation.seeds.map(esc).join(', ')}</p>`:''}</details>
        <details><summary>이 실행의 로그</summary><pre>${esc((job.logs||[]).join('\n'))}</pre></details></article>`;
    }).join(''):'<div class="card-empty"><strong>표시할 기록이 없습니다.</strong><p>새 학습을 시작하거나 검색 조건을 바꿔보세요.</p></div>';
    $('trainingHistory').querySelectorAll('[data-policy-eval]').forEach(button=>button.onclick=()=>evaluate(button.dataset.policyEval));
    const evaluations=history.filter(job=>job.evaluation);
    $('trainingRecordCount').textContent=history.filter(job=>job.kind!=='evaluation').length;
    $('evaluationRecordCount').textContent=evaluations.length;
    const evaluationSignature=JSON.stringify(evaluations.map(({logs,...job})=>job));
    if(evaluationSignature!==evaluationsRendered){
      evaluationsRendered=evaluationSignature;
    $('policyEvaluations').innerHTML=evaluations.length?`<div class="cards-section-label"><strong>최근 평가 결과</strong><span>최근 ${Math.min(6,evaluations.length)}개 · 전체 ${evaluations.length}개</span></div><div class="evaluation-card-grid">${evaluations.slice(0,6).map(job=>`<article class="evaluation-result-card"><div class="evaluation-card-heading"><span>${esc(names[job.policy])}</span><small>${esc(environments[environmentOf(job.config)].name)}</small></div>${successCard('측정 성공률',{...job.evaluation})}<div class="evaluation-card-meta"><p>${job.evaluation.input==='pixels_agent_pos'?'영상 + 로봇 위치':esc(environments[environmentOf(job.config)].input)}</p><p>${job.evaluation.episodes}개 · 최대 ${job.evaluation.step_limit}스텝</p><details><summary>평가 조건과 실행 영상</summary><p>원본 <code>${esc(job.config.source_job)}</code></p><p>Seed ${job.evaluation.seeds.map(esc).join(', ')}</p>${(job.videos || []).map(path=>`<video controls playsinline preload="none" src="${esc(mediaUrl(path))}"></video>`).join('')}</details></div></article>`).join('')}</div><details class="evaluation-all"><summary>전체 ${evaluations.length}개 평가 비교표</summary><div class="table-scroll"><table><thead><tr><th>정책</th><th>입력</th><th>성공률</th><th>평균 최고 보상</th><th>평가 조건</th></tr></thead><tbody>${evaluations.map(job=>`<tr><td>${esc(environments[environmentOf(job.config)].name)} · ${esc(names[job.policy])}<br><small>${esc(job.config.source_job.slice(0,8))}</small></td><td>${job.evaluation.input==='pixels_agent_pos'?'영상 + 로봇 위치':esc(environments[environmentOf(job.config)].input)}</td><td>${(job.evaluation.success_rate*100).toFixed(1)}%</td><td>${job.evaluation.mean_best_reward.toFixed(3)}</td><td>${job.evaluation.episodes}개 · 최대 ${job.evaluation.step_limit}스텝<br><small>Seed ${job.evaluation.seeds.map(esc).join(', ')}</small></td></tr>`).join('')}</tbody></table></div></details>`:'<div class="card-empty"><span>◎</span><strong>첫 정책 평가를 기다리고 있습니다.</strong><p>학습 기록 카드에서 정책을 선택해 평가하세요.</p></div>';
    }
    controls();
  }
  async function refresh() {
    const responses = await Promise.all([api('/api/training/current'),api('/api/training'), methods.length ? Promise.resolve(methods) : api('/api/training/methods')]);
    [state, history, methods] = responses;
    const status = state.kind === 'evaluation' && state.status==='completed' ? '정책 평가 완료' : statuses[state.status] || state.status;
    $('trainingStatus').parentElement.parentElement.dataset.status=state.status;
    $('trainingStatus').textContent = state.policy ? `${names[state.policy]} · ${status}` : status;
    $('trainingLogs').textContent = (state.logs || []).join('\n');
    await learning.refresh();
    renderHistory(); configure();
  }
  async function evaluate(source) {
    error(''); submitting=true; controls();
    try {
      state = await api('/api/training/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_job:source,device:$('trainingDevice').value,episodes:Number($('policyEvalEpisodes').value),step_limit:Number($('policyEvalSteps').value)})});
      await refresh();
    } catch(e) { error(e.message); }
    finally { submitting=false; controls(); }
  }
  $('trainingHistoryFilter').onchange=()=>{visibleRecords=6;renderHistory();};
  $('trainingHistorySearch').oninput=()=>{visibleRecords=6;renderHistory();};
  $('trainingHistoryMore').onclick=()=>{visibleRecords+=6;renderHistory();};
  document.querySelectorAll('[data-lesson-method]').forEach(button=>button.onclick=()=>{
    if($('trainingAlgorithm').disabled)return;
    $('trainingAlgorithm').value=button.dataset.lessonMethod;
    $('trainingAlgorithm').dispatchEvent(new Event('change',{bubbles:true}));
  });
  $('trainingDevice').onchange=()=>configure();
  $('trainingAlgorithm').onchange = () => { $('trainingSteps').value = $('trainingAlgorithm').value==='ppo' ? 1024 : 1000; sourceRendered=''; configure(true); };
  $('trainingEnvironment').onchange = () => { $('trainingDataset').value=environments[$('trainingEnvironment').value].dataset; sourceRendered=''; configure(true); };
  $('trainingMode').onchange = () => configure(true);
  $('trainingSource').onchange = () => configure(true);
  $('trainingForm').onsubmit = async event => {
    event.preventDefault(); error(''); submitting=true; controls();
    const body = {algorithm:$('trainingAlgorithm').value, environment:$('trainingEnvironment').value, mode:$('trainingMode').value, preset:$('trainingPreset').value,
                  device:$('trainingDevice').value,steps:Number($('trainingSteps').value),batch_size:Number($('trainingBatch').value),seed:Number($('trainingSeed').value)};
    if (rl()) Object.assign(body,{learning_rate:Number($('trainingLearningRate').value),gamma:Number($('trainingGamma').value),rollout_steps:Number($('trainingRollout').value)});
    else Object.assign(body,{dataset:$('trainingDataset').value.trim(),episodes:Number($('trainingEpisodes').value)});
    if (body.mode !== 'new') body.source_job=$('trainingSource').value;
    try { state=await api('/api/training',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); await refresh(); }
    catch(e) { error(e.message); }
    finally { submitting=false; controls(); }
  };
  $('trainingStop').onclick = async () => {
    try { state=await api('/api/training/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); await refresh(); }
    catch(e) { error(e.message); }
  };
  return {refresh,isRunning};
}
