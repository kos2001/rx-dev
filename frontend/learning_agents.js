import {successCard,statusBadge} from './learning_cards.js';
import {environments,environmentOf,canEvaluate} from './learning_environments.js';
export function connectLearningAgents({api, error, getHistory, device, busy, onChange}) {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names = {act:'ACT',diffusion:'Diffusion',ppo:'PPO',sac:'SAC'};
  const stages = {learning_analyst:'학습 분석',learning_designer:'실험 설계',train_baseline:'기준 학습',evaluate_baseline:'기준 평가',train_candidate:'후보 학습',evaluate_candidate:'후보 평가',learning_reviewer:'독립 검토',preflight:'실행 환경 확인',development_verification:'개발 평가 검증',holdout_baseline:'기준 최종 평가',holdout_candidate:'후보 최종 평가',counterexample_verification:'반례 검증',completed:'완료'};
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
    $('learningAgentResume').hidden=state.harness_version!==1 || !['interrupted','failed','cancelled'].includes(state.status);
    $('learningAgentResume').disabled=isRunning() || busy() || !connected;
    $('learningAgentForm').querySelectorAll('input,select').forEach(e=>e.disabled=isRunning());
    onChange();
  }
  function render() {
    $('learningAgentStatus').textContent=state.status==='running'?`실행 중 · ${stages[state.stage] || state.stage}`:state.status==='completed'?'학습 Agent 실험 완료':state.error || {idle:'학습 Agent 대기',cancelled:'실험 중지됨',interrupted:'서버 재시작으로 중단됨'}[state.status] || state.status;
    $('learningOverviewStatus').textContent={idle:'대기',running:'실행 중',completed:'완료',failed:'실패',cancelled:'중지',interrupted:'중단'}[state.status] || state.status;
    $('learningAgentStatus').closest('.execution-card').dataset.status=state.status;
    const signature=JSON.stringify(state);
    if (signature===resultSignature) return;
    resultSignature=signature;
    const comparison=state.comparison;
    const roleMeta={learning_analyst:{name:'학습 분석 Agent',icon:'⌕',description:'학습 지표와 실패 사례에서 다음 실험의 근거를 찾습니다.'},learning_designer:{name:'실험 설계 Agent',icon:'↗',description:'설정 하나를 바꾸는 비교 실험과 가설을 제안합니다.'},learning_reviewer:{name:'독립 검토 Agent',icon:'✓',description:'측정 결과와 한계를 검토해 개선 여부를 확인합니다.'}};
    const roles=Object.entries(roleMeta).map(([role,meta],index)=>{
      const value=state.roles?.[role], output=value?.output;
      let content=`<p class="role-description">${esc(meta.description)}</p>`;
      if(output){
        const summary=output.summary || output.hypothesis;
        content=`<p class="role-description">${esc(summary.length>180?summary.slice(0,180)+'…':summary)}</p>`;
        if(role==='learning_designer')content+=`<div class="proposal-change"><span>${esc(parameters[output.change.parameter])}</span><strong>${esc(state.baseline_config[output.change.parameter])} <i>→</i> ${esc(output.change.value)}</strong></div>`;
        content+=`<details><summary>전체 ${role==='learning_analyst'?'분석':role==='learning_designer'?'제안':'검토'}와 근거</summary>`;
        if(role==='learning_analyst')content+=`<p>${esc(output.summary)}</p>${output.findings.map(f=>`<p><strong>${esc(f.metric)}</strong></p><p>${esc(f.evidence)}</p><p>${esc(f.recommendation)}</p>`).join('')}`;
        if(role==='learning_designer')content+=`<p>${esc(output.hypothesis)}</p><p>${esc(output.rationale)}</p>`;
        if(role==='learning_reviewer')content+=`<p>${esc(output.summary)}</p><ul>${output.evidence.map(v=>`<li>${esc(v)}</li>`).join('')}</ul><p>${output.limitations.map(esc).join(' ')}</p><p>${esc(output.next_step)}</p>`;
        content+='</details>';
      }
      return `<article class="training-record agent-role-card"><div class="role-card-heading"><span class="role-symbol">${meta.icon}</span>${statusBadge(value?.status || 'idle',{completed:'완료',started:'준비 중',running:'실행 중'}[value?.status] || value?.status || '대기')}</div><span class="role-number">ROLE 0${index+1}</span><h3>${esc(meta.name)}</h3>${content}${value?`<details><summary>스킬과 실행 기록</summary><p><code>${esc(state.skills[role])}</code></p><p>Run <code>${esc(value.run_id)}</code></p></details>`:''}</article>`;
    }).join('');
    const measured=comparison?`<section class="comparison-card"><div class="comparison-heading"><div><p class="eyebrow">DEVELOPMENT EVALUATION</p><h3>개발 평가 · 기준과 후보</h3></div>${statusBadge(comparison.measured_verdict,{improved:'성공 수 증가',regressed:'성공 수 감소',inconclusive:'성공 수 동일 · 결론 유보'}[comparison.measured_verdict])}</div><div class="paired-stat-grid">${['baseline','candidate'].map(name=>successCard(name==='baseline'?'기준 정책':'후보 정책',comparison[name],{seconds:comparison.training[name].seconds})).join('')}</div><details><summary>같은 조건에서 비교한 개발 평가</summary><p>학습 Seed ${comparison.training_seed} · 평가 Seed ${comparison.seeds.map(esc).join(', ')}</p><p class="muted">적은 평가 표본과 한 학습 Seed의 개발 실험입니다. 성공률의 유의한 개선이나 일반화를 입증하지 않습니다.</p></details></section>`:'';
    const phases=[['학습 분석',state.roles?.learning_analyst?.status],['실험 설계',state.roles?.learning_designer?.status],['기준·후보 비교',state.comparison && (state.holdout || !state.harness_version)?'completed':/^(train_|evaluate_|holdout_)/.test(state.stage)?'running':'idle'],['독립 검토',state.roles?.learning_reviewer?.status]];
    const phaseCards=`<ol class="agent-phase-cards" aria-label="Agent 실험 단계">${phases.map(([name,status],i)=>`<li data-status="${esc(status || 'idle')}"><span>${status==='completed'?'✓':String(i+1).padStart(2,'0')}</span><strong>${name}</strong><small>${{completed:'완료',running:'실행 중',started:'준비 중'}[status] || '대기'}</small></li>`).join('')}</ol>`;
    $('learningAgentResults').innerHTML=phaseCards+(state.id?`<p class="experiment-context">${esc(environments[environmentOf(state.baseline_config)].name)} · ${esc(names[state.algorithm])} <code>${esc(state.id.slice(0,8))}</code></p>`:'')+measured+harnessEvidence(state)+`<div class="cards-section-label"><strong>Agent 역할과 결과</strong><span>역할별 독립 세션</span></div><div class="agent-role-grid">${roles}</div>`+(state.id?`<details class="linked-records"><summary>연결된 학습·평가 기록 ${Object.keys(state.children || {}).length}개</summary><p>실험 <code>${esc(state.id)}</code></p>${Object.entries(state.children || {}).map(([stage,id])=>`<p>${esc(stages[stage])} <code>${esc(id)}</code></p>`).join('')}<p>아래 학습 기록에서 체크포인트·로그·평가 영상을 확인할 수 있습니다.</p></details>`:'');
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
    try {state=await api('/api/learning-agents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_job:$('learningAgentSource').value,steps:Number($('learningAgentSteps').value),eval_episodes:Number($('learningAgentEpisodes').value),holdout_episodes:Number($('learningAgentHoldout').value),step_limit:Number($('learningAgentLimit').value),device:device()})}); render();}
    catch(e){error(e.message);} finally{submitting=false;configure();}
  };
  $('learningAgentStop').onclick=async()=>{
    try{state=await api('/api/learning-agents/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});render();configure();}catch(e){error(e.message);}
  };
  $('learningAgentResume').onclick=async()=>{
    submitting=true;configure();error('');
    try{state=await api('/api/learning-agents/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:state.id})});render();}
    catch(e){error(e.message);}finally{submitting=false;configure();}
  };
  function harnessEvidence(record) {
    if(record.harness_version!==1)return '';
    const outcome={verified_improvement:'최종 표본에서 개선 확인',invalid_evidence:'근거 불일치',regressed:'최종 평가 퇴행',inconclusive:'결론 유보'};
    const ledger=record.verification?.holdout;
    const holdout=record.holdout;
    const decision=record.decision;
    return `<article class="training-record harness-evidence comparison-card"><div class="comparison-heading"><div><p class="eyebrow">HOLDOUT & COUNTEREXAMPLES</p><h3>별도 최종 평가와 반례 검증</h3></div>${decision?statusBadge(decision.verdict,outcome[decision.verdict]):statusBadge("idle","평가 대기")}</div>
      <p>${holdout?'후보를 고정한 뒤 새로운 Seed로 평가했습니다.':'후보를 고정한 뒤 개발 평가와 다른 Seed로 최종 평가합니다.'}</p>
      ${holdout?`<div class="paired-stat-grid">${["baseline","candidate"].map(name=>successCard(name==="baseline"?"기준 정책":"후보 정책",holdout[name],{interval:true})).join('')}</div><p class="evaluation-seeds">최종 평가 Seed: ${holdout.seeds.map(esc).join(', ')}</p>`:''}
      ${decision?`<p>최종 판단: <strong>${esc(outcome[decision.verdict])}</strong> · 짝지은 검정 p=${decision.paired_p_value.toFixed(4)}</p><p class="muted">한 학습 Seed와 이번 표본에 한정한 결과이며, 모델을 자동 채택하지 않습니다.</p>`:''}
      ${ledger?`<details open><summary>반례와 검증 근거</summary><p>후보만 성공 ${ledger.resolver.success_gains}회 · 후보만 실패 ${ledger.resolver.success_losses}회</p><p>퇴행 Seed: ${ledger.resolver.regression_seeds.map(esc).join(', ') || '없음'}</p><p>두 정책 모두 실패한 Seed: ${ledger.challenger.shared_failure_seeds.map(esc).join(', ') || '없음'}</p><p>성공 상태 유지: ${ledger.retention_verified?'기록에서 확인':'미확인 또는 유지 실패'}</p><p>성공 유지 실패: ${ledger.challenger.retention_failures.map(v=>`${esc(v.arm)} · ${esc(v.seed)}`).join(', ') || '없음'}</p><p>종료 상태 기록 누락: ${ledger.challenger.missing_terminal_evidence.length}개</p><p>보상만 증가하고 성공 수는 늘지 않은 사례: ${ledger.challenger.reward_only_improvement?'해당':'해당 없음'}</p>${ledger.issues.map(v=>`<p>${esc(v)}</p>`).join('')}</details>`:''}
      <details><summary>실험 진행 기록과 재현 정보</summary>${(record.events || []).map(v=>`<p>${esc(stages[v.stage] || v.stage)} · ${esc(new Date(v.at*1000).toLocaleString())}</p>`).join('')}<p>학습 Seed ${esc(record.training_seed)}</p><p>원본 보상·성공 기록 검증 ${Object.values(record.child_receipts || {}).reduce((count,v)=>count+(v.native_traces?.length || 0),0)}개</p><p>체크포인트 SHA-256 검증 기록 ${Object.keys(record.checkpoint_receipts || {}).length}개</p><pre>${esc(JSON.stringify(record.runtime_versions,null,2))}</pre></details>
    </article>`;
  }
  return {refresh,isRunning};
}
