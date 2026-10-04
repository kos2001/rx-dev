import {connectLearningAgents} from './learning_agents.js';
import {environments,environmentOf,canEvaluate} from './learning_environments.js';
export function connectTraining({api, mediaUrl, error, busy}) {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const statuses = {idle:'학습 대기',running:'실행 중 · 준비 시간 포함',stopping:'중지 중',stopped:'학습 중지됨',completed:'학습 완료 · 체크포인트 저장됨',failed:'실행 실패 · 로그를 확인하세요',interrupted:'서버 재시작으로 중단됨'};
  const names = {act:'ACT',diffusion:'Diffusion Policy',ppo:'PPO',sac:'SAC'};
  let state = {status:'idle'}, submitting = false, history = [], methods = [], historyRendered = '', sourceRendered = '';
  const rl = () => ['ppo','sac'].includes($('trainingAlgorithm').value);
  const ownRunning = () => submitting || ['running','stopping'].includes(state.status);
  const learning = connectLearningAgents({api,error,getHistory:()=>history,device:()=>$('trainingDevice').value,busy:()=>ownRunning() || busy(),onChange:controls});
  const isRunning = () => ownRunning() || learning.isRunning();
  const eligible = () => history.filter(job => job.kind !== 'evaluation' && environmentOf(job.config) === $('trainingEnvironment').value && job.policy === $('trainingAlgorithm').value && job.checkpoints.length && !['running','stopping'].includes(job.status));
  function controls() {
    const blocked = isRunning() || busy();
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
    const method = methods.find(item => item.id === algorithm);
    $('trainingMethodInfo').textContent = method ? `${environment.name} · ${method.description} 입력: ${rl()?environment.input:method.input} · ${method.engine}` : '';
    $('trainingNotes').textContent = rl() ? `${environment.name}에서 경험을 직접 수집합니다. ${environment.input}를 입력으로 받고, 환경의 기본 보상을 사용합니다. 영상 모델과 입력 조건이 다릅니다. PPO 스텝은 경험 수집 간격의 배수여야 합니다. 모델과 로그는 로컬에 저장됩니다.` : '처음 N개 시연 에피소드를 사용합니다. 작은 모델은 로컬 실험용으로 구조를 줄인 설정입니다. 미세조정은 가중치를 가져와 새 optimizer로 학습하고, 재개는 optimizer와 스텝을 복원합니다. 데이터셋과 영상 인코더 초기 가중치를 다운로드하며 결과는 로컬에 저장됩니다.';
    controls();
  }
  function renderHistory() {
    const signature = JSON.stringify(history.map(({logs,...job}) => job));
    if (signature === historyRendered) return;
    historyRendered = signature;
    $('trainingHistory').innerHTML = history.length ? history.map(job => {
      const evaluation = job.kind === 'evaluation', config = job.config;
      const text = evaluation ? `${config.episodes}개 평가 · 최대 ${config.step_limit}스텝` : config.dataset ? `${config.dataset} · ${config.steps}업데이트 · ${config.episodes}에피소드` : `${environments[environmentOf(config)].name} 상태 입력 · ${config.steps}환경 스텝`;
      const saved = !evaluation && job.checkpoints.length && !['running','stopping'].includes(job.status);
      return `<article class="training-record"><strong>${environments[environmentOf(config)].name} · ${names[job.policy] || esc(job.policy)} · ${evaluation?'시뮬레이터 평가':{new:'새 학습',finetune:'미세조정',resume:'이어 학습'}[config.mode] || '학습'}</strong><p>${esc(evaluation && job.status==='completed' ? '정책 평가 완료' : statuses[job.status] || job.status)} · ${esc(config.device)} · ${esc(text)}</p><small>${esc(new Date(job.started_at*1000).toLocaleString())} · ${esc(job.id)}</small>${config.source_job ? `<p>원본 학습 기록: <code>${esc(config.source_job)}</code></p>` : ''}<p>${job.checkpoints.length ? job.checkpoints.map(path=>`<code>${esc(path)}</code>`).join('<br>') : evaluation ? '' : '저장된 체크포인트 없음'}</p>${saved && canEvaluate(config) ? `<div class="training-actions"><button class="primary" data-policy-eval="${job.id}">정책 평가 →</button></div>` : ''}${job.evaluation ? `<p>성공률 ${(job.evaluation.success_rate*100).toFixed(1)}% · 평균 최고 보상 ${job.evaluation.mean_best_reward.toFixed(3)} · Seed ${job.evaluation.seeds.join(', ')}</p>` : ''}${job.videos?.length ? `<details><summary>평가 영상 ${job.videos.length}개</summary>${job.videos.map(path=>`<video controls preload="metadata" src="${esc(mediaUrl(path))}"></video>`).join('')}</details>` : ''}<details><summary>이 실행의 로그</summary><pre>${esc((job.logs||[]).join('\n'))}</pre></details></article>`;
    }).join('') : '<p class="muted">아직 학습 기록이 없습니다.</p>';
    $('trainingHistory').querySelectorAll('[data-policy-eval]').forEach(button => button.onclick = () => evaluate(button.dataset.policyEval));
    const evaluations = history.filter(job=>job.evaluation);
    $('policyEvaluations').innerHTML = evaluations.length ? `<div class="table-scroll"><table><thead><tr><th>정책</th><th>입력</th><th>성공률</th><th>평균 최고 보상</th><th>평가 조건</th></tr></thead><tbody>${evaluations.map(job=>`<tr><td>${environments[environmentOf(job.config)].name} · ${names[job.policy]}<br><small>${job.config.source_job.slice(0,8)}</small></td><td>${job.evaluation.input==='pixels_agent_pos'?'영상 + 로봇 위치':environments[environmentOf(job.config)].input}</td><td>${(job.evaluation.success_rate*100).toFixed(1)}%</td><td>${job.evaluation.mean_best_reward.toFixed(3)}</td><td>${job.evaluation.episodes}개 · 최대 ${job.evaluation.step_limit}스텝<br><small>Seed ${job.evaluation.seeds.join(', ')}</small></td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">아직 정책 평가 기록이 없습니다.</p>';
  }
  async function refresh() {
    const responses = await Promise.all([api('/api/training/current'),api('/api/training'), methods.length ? Promise.resolve(methods) : api('/api/training/methods')]);
    [state, history, methods] = responses;
    const status = state.kind === 'evaluation' && state.status==='completed' ? '정책 평가 완료' : statuses[state.status] || state.status;
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
