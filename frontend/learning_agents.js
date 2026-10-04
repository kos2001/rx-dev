import {environments,environmentOf,canEvaluate} from './learning_environments.js';
export function connectLearningAgents({api, error, getHistory, device, busy, onChange}) {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names = {act:'ACT',diffusion:'Diffusion',ppo:'PPO',sac:'SAC'};
  const stages = {learning_analyst:'학습 분석',learning_designer:'실험 설계',train_baseline:'기준 학습',evaluate_baseline:'기준 평가',train_candidate:'후보 학습',evaluate_candidate:'후보 평가',learning_reviewer:'독립 검토',completed:'완료'};
  const parameters={batch_size:'배치 크기',steps:'학습 스텝',learning_rate:'학습률',gamma:'미래 보상 할인율'};
  let state={status:'idle'}, submitting=false, connected=false, checked=0, sourceSignature='', resultSignature='';
  const isRunning=()=>submitting || state.status==='running';
  function configure() {
    const source=getHistory().find(j=>j.id===$('learningAgentSource').value);
    const rl=source && ['ppo','sac'].includes(source.policy);
    const input=$('learningAgentSteps');
    input.min=source?.policy==='ppo'?128:source?.policy==='sac'?64:1;
    input.max=rl?2048:512; input.step=source?.policy==='ppo'?128:1;
    if (Number(input.value)<Number(input.min) || Number(input.value)>Number(input.max) || source?.policy==='ppo' && Number(input.value)%128) input.value=128;
    $('learningAgentStart').disabled=isRunning() || busy() || !connected || !source;
    $('learningAgentStop').hidden=state.status!=='running';
    $('learningAgentForm').querySelectorAll('input,select').forEach(e=>e.disabled=isRunning());
    onChange();
  }
  function render() {
    $('learningAgentStatus').textContent=state.status==='running'?`실행 중 · ${stages[state.stage] || state.stage}`:state.status==='completed'?'학습 Agent 실험 완료':state.error || {idle:'학습 Agent 대기',cancelled:'실험 중지됨',interrupted:'서버 재시작으로 중단됨'}[state.status] || state.status;
    const signature=JSON.stringify(state);
    if (signature===resultSignature) return;
    resultSignature=signature;
    const comparison=state.comparison;
    const roles=Object.entries(state.roles || {}).map(([role,value])=>{
      const output=value.output;
      let content='<p class="muted">응답 대기 중</p>';
      if(output && role==='learning_analyst') content=`<p>${esc(output.summary)}</p><details><summary>분석 근거 ${output.findings.length}개</summary>${output.findings.map(f=>`<p><strong>${esc(f.metric)}</strong></p><p>${esc(f.evidence)}</p><p>${esc(f.recommendation)}</p>`).join('')}</details>`;
      if(output && role==='learning_designer') content=`<p><strong>변경: ${esc(parameters[output.change.parameter])} ${state.baseline_config[output.change.parameter]} → ${esc(output.change.value)}</strong></p><p>${esc(output.hypothesis)}</p><details><summary>설계 근거</summary><p>${esc(output.rationale)}</p></details>`;
      if(output && role==='learning_reviewer') content=`<p>${esc(output.summary)}</p><p class="muted">${output.limitations.map(esc).join(' ')}</p><p>${esc(output.next_step)}</p><details><summary>검토 근거</summary><ul>${output.evidence.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></details>`;
      return `<article class="training-record"><strong>${esc(value.name)} · ${esc({completed:'완료',started:'준비 중',running:'실행 중'}[value.status] || value.status)}</strong>${content}<details><summary>적용 스킬과 실행 기록</summary><p>스킬: <code>${esc(state.skills[role])}</code></p><p>Run <code>${esc(value.run_id)}</code></p></details></article>`;
    }).join('');
    const measured=comparison?`<p>판정: <strong>${esc({improved:'성공 수 증가',regressed:'성공 수 감소',inconclusive:'성공 수 동일 · 결론 유보'}[comparison.measured_verdict])}</strong> · 같은 학습 Seed ${comparison.training_seed} · 평가 Seed ${comparison.seeds.join(', ')}</p><div class="table-scroll"><table><thead><tr><th>정책</th><th>성공</th><th>최고 보상 평균</th><th>학습 시간</th></tr></thead><tbody>${['baseline','candidate'].map(name=>`<tr><td>${name==='baseline'?'기준':'후보'}</td><td>${comparison[name].successes}/${comparison[name].episodes}</td><td>${comparison[name].mean_best_reward.toFixed(3)}</td><td>${comparison.training[name].seconds.toFixed(1)}초</td></tr>`).join('')}</tbody></table></div><p class="muted">적은 평가 표본과 한 학습 Seed의 개발 실험입니다. 성공률의 유의한 개선이나 일반화를 입증하지 않습니다.</p>`:'';
    $('learningAgentResults').innerHTML=(state.id?`<p><strong>${environments[environmentOf(state.baseline_config)].name} · ${names[state.algorithm]}</strong></p>`:'')+measured+roles+(state.id?`<details><summary>연결된 학습·평가 기록</summary><p>실험 <code>${esc(state.id)}</code></p>${Object.entries(state.children || {}).map(([stage,id])=>`<p>${esc(stages[stage])} <code>${esc(id)}</code></p>`).join('')}<p>아래 학습 기록에서 체크포인트·로그·평가 영상을 확인할 수 있습니다.</p></details>`:'');
  }
  async function refresh() {
    state=await api('/api/learning-agents/current');
    if (Date.now()-checked>10000) {
      checked=Date.now();
      const health=await api('/api/agents/health'); connected=health.connected===true;
      $('learningAgentHealth').textContent=connected?'Hermes 연결됨 · 역할마다 독립 세션':'Hermes 연결을 확인하세요. Agent 실험에는 모델 연결이 필요합니다.';
    }
    const sources=getHistory().filter(j=>j.kind!=='evaluation' && j.status==='completed' && j.checkpoints.length && canEvaluate(j.config));
    const signature=JSON.stringify(sources.map(j=>j.id));
    if (signature!==sourceSignature) {
      sourceSignature=signature; const selected=$('learningAgentSource').value;
      $('learningAgentSource').innerHTML=sources.map(j=>`<option value="${j.id}">${environments[environmentOf(j.config)].name} · ${names[j.policy]} · ${j.id.slice(0,8)}</option>`).join('');
      if(sources.some(j=>j.id===selected)) $('learningAgentSource').value=selected;
    }
    render(); configure();
  }
  $('learningAgentSource').onchange=configure;
  $('learningAgentForm').onsubmit=async event=>{
    event.preventDefault(); error(''); submitting=true; configure();
    try {state=await api('/api/learning-agents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_job:$('learningAgentSource').value,steps:Number($('learningAgentSteps').value),eval_episodes:Number($('learningAgentEpisodes').value),step_limit:Number($('learningAgentLimit').value),device:device()})}); render();}
    catch(e){error(e.message);} finally{submitting=false;configure();}
  };
  $('learningAgentStop').onclick=async()=>{
    try{state=await api('/api/learning-agents/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});render();configure();}catch(e){error(e.message);}
  };
  return {refresh,isRunning};
}
