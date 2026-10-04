// Client calls only the application API. Hermes bearer keys never enter the browser.
export function connectAgents({api, mediaUrl, reportId, reportKind, error, simulationRunning}) {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let health = {}, state = {status:'idle'}, busy = false, rendered = '', lastHealth = 0;
  const roleLabel = {analyst:'실패 분석 Agent',designer:'실험 설계 Agent',reviewer:'독립 검증 Agent'};
  const stageLabel = {analyst:'실패 분석 중',designer:'개선 설정 설계 중',simulation:'새 초기 조건에서 물리 시뮬레이션 비교 중',reviewer:'실제 측정 결과 독립 검토 중'};
  const verdictLabel = {improved:'성공 수 증가 · 추가 검증 필요',inconclusive:'성공 수 동일 · 개선 결론 보류',regressed:'성공 수 감소 · 후보 채택 보류'};
  function render() {
    const running = state.status === 'running';
    const sameReport = state.report_id === reportId();
    $('hermesConnection').textContent = health.connected ? 'rx-dev 연결됨 · 분석 / 설계 / 검증 역할 분리' : health.error || 'Hermes 연결 대기';
    $('agentRun').disabled = !health.connected || running || simulationRunning() || reportKind() !== 'agent';
    $('agentRun').textContent = running ? 'Agent 개선 실험 중…' : 'Agent 개선 실험 →';
    $('agentStop').hidden = !running;
    for (const name of ['analyst','designer','simulation','reviewer']) {
      const element = $(`stage${name[0].toUpperCase()+name.slice(1)}`);
      element.className = running && state.stage === name ? 'active' : sameReport && (state.roles?.[name]?.status === 'completed' || name === 'simulation' && state.evaluation) ? 'done' : '';
    }
    $('agentProgress').textContent = running ? `${stageLabel[state.stage] || state.stage} · ${sameReport ? '현재 기록' : '다른 평가 기록'} · 새 Seed ${(state.evaluation_seeds||[]).join(', ')}` : sameReport && state.status === 'completed' ? `완료 · ${verdictLabel[state.evaluation.measured_verdict]} · 기존 제어기는 유지됩니다.` : sameReport && ['failed','cancelled','interrupted'].includes(state.status) ? `${{failed:'실패',cancelled:'중지됨',interrupted:'중단됨'}[state.status]} · ${state.error || ''}` : '현재 평가를 바탕으로 개선 가설을 세우고 직접 검증합니다.';
    const results = sameReport ? state.roles || {} : {};
    $('agentResults').hidden = !Object.keys(results).length;
    const signature = JSON.stringify([reportId(), state.id, results, state.evaluation, state.recordings]);
    if (signature === rendered) return;
    rendered = signature;
    let html = '';
    for (const name of ['analyst','designer','reviewer']) {
      const role = results[name]; if (!role) continue;
      const out = role.output;
      html += `<article class="agent-result"><h3>${roleLabel[name]}</h3><small>Hermes run · ${esc(role.run_id)} · ${esc(role.status)}</small>`;
      if (!out) html += '<p>Agent가 기록을 검토하고 있습니다.</p>';
      else if (name === 'analyst') html += `<p>${esc(out.summary)}</p><details><summary>실패 근거와 개선 제안 ${out.findings.length}건</summary><ul>${out.findings.map(f=>`<li><strong>${esc(f.failure)}</strong> · Seed ${esc(f.seeds.join(', '))}<br>${esc(f.evidence)}<br>제안: ${esc(f.recommendation)}</li>`).join('')}</ul></details>`;
      else if (name === 'designer') html += `<p>${esc(out.hypothesis)}</p><code>${esc(JSON.stringify(out.settings,null,2))}</code><details><summary>설정 변경 근거</summary><p>${esc(out.rationale)}</p></details>`;
      else html += `<p>${esc(out.summary)}</p><details><summary>측정 근거와 한계</summary><ul>${out.evidence.map(e=>`<li>${esc(e)}</li>`).join('')}</ul><p>한계: ${esc(out.limitations.join(' / '))}</p></details><p>다음: ${esc(out.next_step)}</p>`;
      html += '</article>';
    }
    if (sameReport && state.evaluation) {
      const e = state.evaluation, old = e.incumbent.summary, candidate = e.candidate.summary;
      const successes = s => `${Math.round(s.success_rate*s.episodes)} / ${s.episodes}`;
      const intervals = e.success_intervals_95;
      const intervalText = range => range.map(v=>(v*100).toFixed(1)+'%').join('–');
      html += `<article class="agent-result agent-comparison"><h3>실제 비교 · ${esc(verdictLabel[e.measured_verdict])}</h3><table><thead><tr><th>측정값</th><th>기존 설정</th><th>Agent 제안 설정</th></tr></thead><tbody><tr><td>성공</td><td>${successes(old)}</td><td>${successes(candidate)}</td></tr><tr><td>평균 최종 보상</td><td>${old.mean_final_reward.toFixed(3)}</td><td>${candidate.mean_final_reward.toFixed(3)}</td></tr><tr><td>평균 실행 시간</td><td>${old.mean_wall_seconds.toFixed(2)}s</td><td>${candidate.mean_wall_seconds.toFixed(2)}s</td></tr></tbody></table><p>최종 보상 기준 ${e.paired_reward.wins}승 / ${e.paired_reward.losses}패 / ${e.paired_reward.ties}동률 · 새 Seed ${esc(e.seeds.join(', '))} · 최대 ${e.steps}스텝</p><small>단일 개발 실험입니다. 통계적 일반화나 실물 로봇 안전성을 입증하지 않습니다.</small></article>`;
      if (intervals) html += `<p class="agent-uncertainty">성공률 95% Wilson 구간: 기존 ${intervalText(intervals.incumbent)} / 후보 ${intervalText(intervals.candidate)} · 탐색 Seed ${esc(e.planner_seed)} 고정</p>`;
    }
    if (sameReport && state.recordings?.status === 'completed') {
      const recordings = state.recordings;
      html += `<article class="agent-result agent-recordings"><div class="recording-heading"><div><h3>Agent 후보 vs 기존 설정 · 실제 비교 영상</h3><p>동일한 초기 상태 · 동일한 최대 스텝 · 녹화 결과와 원래 평가 수치 일치 확인</p></div><label>초기 조건<select id="agentVideoSeed" aria-label="Agent 비교 영상 초기 조건">${recordings.pairs.map(pair=>`<option value="${pair.seed}">Seed ${pair.seed}${recordings.recommended_seeds.includes(pair.seed)?' · 성공/실패 대조':''}</option>`).join('')}</select></label></div><div class="recording-pair"><div><h4>기존 MPC 설정 <span id="incumbentVideoBadge"></span></h4><video id="incumbentVideo" controls playsinline preload="metadata"></video><p id="incumbentVideoResult"></p><a id="incumbentVideoDownload" download>영상 다운로드 ↗</a></div><div><h4>Agent 제안 설정 <span id="candidateVideoBadge"></span></h4><video id="candidateVideo" controls playsinline preload="metadata"></video><p id="candidateVideoResult"></p><a id="candidateVideoDownload" download>영상 다운로드 ↗</a></div></div><div class="recording-controls"><button id="agentVideoPlay">동시 재생</button><button id="agentVideoReset">처음으로</button><input id="agentVideoTime" type="range" min="0" max="30" step="0.1" value="0" aria-label="Agent 비교 영상 재생 시간"><span id="agentVideoClock">0.0s</span></div><p id="agentVideoComparison"></p><small>먼저 종료된 영상은 마지막 화면에 머뭅니다. 영상은 행동 직전 상태를 표시하며, 성공·최종 보상은 행동 후 공식 측정값입니다. 아래 원래 평가 영상과 구분해 주세요.</small></article>`;
    }
    $('agentResults').innerHTML = html;
    if (sameReport && state.recordings?.status === 'completed') bindRecordings(state.recordings);
  }
  function bindRecordings(recordings) {
    const videos = [$('incumbentVideo'),$('candidateVideo')];
    let simultaneous = false;
    function pause() {simultaneous=false;videos.forEach(v=>v.pause());$('agentVideoPlay').textContent='동시 재생';}
    function select() {
      pause();
      const pair = recordings.pairs.find(p=>p.seed===Number($('agentVideoSeed').value));
      for (const name of ['incumbent','candidate']) {
        const recorded = pair[name], result = recorded.result, video = $(`${name}Video`);
        video.src=mediaUrl(recorded.video);video.poster=mediaUrl(recorded.poster);
        $(`${name}VideoBadge`).textContent=result.success?'성공':'미완료';
        $(`${name}VideoResult`).textContent=`최종 보상 ${result.final_reward.toFixed(3)} · ${result.steps}스텝 · 위치 오차 ${result.position_error.toFixed(1)} · 각도 오차 ${result.angle_error.toFixed(3)}rad`;
        $(`${name}VideoDownload`).href=mediaUrl(recorded.video);
      }
      $('agentVideoTime').max=Math.max(pair.incumbent.result.steps,pair.candidate.result.steps)/recordings.fps;
      $('agentVideoTime').value=0;$('agentVideoClock').textContent='0.0s';
      const old=pair.incumbent.result, candidate=pair.candidate.result;
      $('agentVideoComparison').textContent = `Seed ${pair.seed}: ${old.success&&!candidate.success?'기존 설정만 성공':!old.success&&candidate.success?'Agent 후보만 성공':old.success?'둘 다 성공':'둘 다 미완료'} · 후보 최종 보상 차이 ${(candidate.final_reward-old.final_reward>=0?'+':'')+(candidate.final_reward-old.final_reward).toFixed(3)}`;
    }
    $('agentVideoSeed').value=recordings.recommended_seeds[0];$('agentVideoSeed').onchange=select;select();
    $('agentVideoPlay').onclick=async()=>{
      if(simultaneous){pause();return;}
      if(videos.every(v=>v.ended))videos.forEach(v=>v.currentTime=0);
      simultaneous=true;$('agentVideoPlay').textContent='동시 일시 정지';
      try{await Promise.all(videos.filter(v=>!v.ended).map(v=>v.play()));}catch(e){pause();error('영상 재생을 시작할 수 없습니다. 영상의 개별 재생 버튼으로 확인해 주세요.');}
    };
    $('agentVideoReset').onclick=()=>{pause();videos.forEach(v=>v.currentTime=0);$('agentVideoTime').value=0;$('agentVideoClock').textContent='0.0s';};
    $('agentVideoTime').oninput=()=>{pause();const t=Number($('agentVideoTime').value);videos.forEach(v=>{if(Number.isFinite(v.duration))v.currentTime=Math.min(t,v.duration);});$('agentVideoClock').textContent=`${t.toFixed(1)}s`;};
    for(const video of videos) {
      video.addEventListener('timeupdate',()=>{if(simultaneous){const t=Math.max(...videos.map(v=>v.currentTime));$('agentVideoTime').value=t;$('agentVideoClock').textContent=`${t.toFixed(1)}s`;}});
      video.addEventListener('ended',()=>{if(videos.every(v=>v.ended))pause();});
    }
  }
  async function poll() {
    if (busy) return; busy = true;
    try {
      if (Date.now() - lastHealth > 30000) {health = await api('/api/agents/health'); lastHealth = Date.now();}
      state = await api('/api/agents/current'); render();
      try {
        const study=await api('/api/controller-study');
        if(study.test?.trials?.length===2 && study.test.trials.every(t=>t.runs.length===study.expected_test_episodes)) {
          const [old,candidate]=study.test.trials;
          $('controllerStudy').hidden=false;
          $('controllerStudy').innerHTML=`<h3>제어기 개선 검증 · 미사용 초기 조건 ${study.expected_test_episodes}개</h3><table><thead><tr><th>측정값</th><th>기존 v1</th><th>개선 후보 v2</th></tr></thead><tbody><tr><td>공식 성공</td><td>${old.runs.filter(r=>r.success).length} / ${old.runs.length}</td><td>${candidate.runs.filter(r=>r.success).length} / ${candidate.runs.length}</td></tr><tr><td>최종 보상</td><td>${old.summary.mean_final_reward.toFixed(3)}</td><td>${candidate.summary.mean_final_reward.toFixed(3)}</td></tr><tr><td>실행 시간</td><td>${old.summary.mean_wall_seconds.toFixed(2)}s</td><td>${candidate.summary.mean_wall_seconds.toFixed(2)}s</td></tr></tbody></table><p>개발 Seed 0–4에서 선택 → 미사용 Seed 300–329에서 평가 · 탐색 난수는 ${study.test.planner_seed}로 고정 · 동일 300스텝</p><small>v2: 실제 T자 표면 접촉, 짧은 종단 밀기, 공식 성공/겹침 우선. phase_steps ${candidate.settings.phase_steps}. 자동 채택하지 않습니다. 이 결과는 위의 LLM 단일 설정 실험과 별도입니다.</small>`;
        }
      }catch(_){/* Older backend versions can still display stored Agent results. */}
    } catch(e) {health.connected = false; health.error = e.message; render();}
    finally {busy = false;}
  }
  $('agentRun').onclick = async () => {
    error(''); $('agentRun').disabled = true;
    try {state = await api('/api/agents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({report_id:reportId()})}); rendered='';render();}
    catch(e) {error(e.message); await poll();}
  };
  $('agentStop').onclick = async () => {
    $('agentStop').disabled=true;
    try {await api('/api/agents/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}
    catch(e) {error(e.message);}
    finally {$('agentStop').disabled=false;}
  };
  poll(); setInterval(poll,2000);
  return {refresh: render, isRunning: () => state.status === 'running'};
}
