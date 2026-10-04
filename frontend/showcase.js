export async function loadShowcase() {
  const root=document.getElementById('successGallery');
  const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const base='assets/success/';
  try {
    const response=await fetch(base+'manifest.json');
    if(!response.ok)throw new Error('Recordings unavailable');
    const data=await response.json();
    const successes=data.runs.filter(run=>run.success && run.final_success);
    const recording=run=>`<video controls playsinline preload="metadata" poster="${base+esc(run.poster)}" aria-label="큐브 전달 ${run.success?'성공':'실패'} 영상 · Seed ${run.seed}"><source src="${base+esc(run.video)}" type="video/mp4">브라우저가 영상 재생을 지원하지 않습니다. <a href="${base+esc(run.video)}">영상 열기</a></video>`;
    root.innerHTML=`<div class="success-cards">${successes.map((run,index)=>`<article class="success-card">${recording(run)}<div class="success-caption"><h3>큐브 전달 완료 <span class="badge success">성공</span></h3><p>실행 ${String(index+1).padStart(2,'0')} · ${run.duration.toFixed(1)}초 · 공식 보상 ${run.max_reward}</p><a href="${base+esc(run.video)}" download>영상 다운로드 ↓</a></div></article>`).join('')}</div>
      <div class="success-context"><p><strong>${esc(data.environment)} · 공개 사전학습 ${esc(data.model)}</strong></p><p>오른팔이 큐브를 집어 왼팔에 전달합니다. 성공 후에도 ${data.runs[0].steps}스텝까지 실행해 최종 성공 상태를 확인했습니다.</p><p class="muted">${data.training_steps.toLocaleString()}스텝 학습 모델 · ${esc(data.recorded_at)} 실행 · <a href="${esc(data.model_url)}" target="_blank" rel="noreferrer">모델 출처 ↗</a></p>
      <details class="success-evidence"><summary>전체 평가 결과 · ${successes.length}/${data.runs.length} 성공</summary><p>${esc(data.success_rule)}. 이 ${data.runs.length}회는 사례 확인이며 일반화 성능을 측정한 벤치마크가 아닙니다.</p><div class="table-scroll"><table><thead><tr><th>초기 조건</th><th>결과</th><th>최고 보상</th><th>최초 성공 스텝</th></tr></thead><tbody>${data.runs.map(run=>`<tr><td>${run.seed}</td><td>${run.success?'성공':'실패'}</td><td>${run.max_reward}</td><td>${run.first_success_step ?? '—'}</td></tr>`).join('')}</tbody></table></div>${data.runs.filter(run=>!run.success).map(run=>`<article class="success-failure"><h3>같은 모델의 실패 실행 · Seed ${run.seed}</h3>${recording(run)}</article>`).join('')}</details></div>`;
  } catch(error) {
    root.textContent='성공 영상 파일을 불러올 수 없습니다. 잠시 후 새로고침해 주세요.';
  }
}
