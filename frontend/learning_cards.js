export const escapeHTML=value=>String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function statusBadge(status,label) {
  const tone=['completed','improved','verified_improvement'].includes(status)?'success':
    ['failed','regressed','invalid_evidence'].includes(status)?'danger':['running','started','stopping'].includes(status)?'active':'neutral';
  return `<span class="card-status ${tone}"><i></i>${escapeHTML(label)}</span>`;
}
export function successCard(label,arm,{seconds,interval=false}={}) {
  const p=arm.success_rate ?? arm.successes/arm.episodes;
  const percent=Math.max(0,Math.min(100,p*100));
  const bounds=interval && arm.success_interval_95;
  return `<article class="success-stat-card"><div class="stat-card-title"><span>${escapeHTML(label)}</span><span>SUCCESS RATE</span></div><div class="success-stat-value"><strong>${percent.toFixed(1)}<small>%</small></strong><span>${arm.successes ?? Math.round(p*arm.episodes)} / ${arm.episodes} 성공</span></div>
    <div class="success-meter" role="meter" aria-label="${escapeHTML(label)} 성공률" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent.toFixed(1)}"><span style="width:${percent}%"></span></div>
    ${bounds?`<div class="confidence-meter" aria-hidden="true"><span style="left:${bounds[0]*100}%;width:${(bounds[1]-bounds[0])*100}%"></span><i style="left:${percent}%"></i></div><p class="confidence-caption">성공률 95% 구간 <strong>${bounds.map(v=>(v*100).toFixed(1)).join('–')}%</strong></p>`:''}
    <div class="stat-card-foot"><span>최고 보상 평균 <b>${Number(arm.mean_best_reward).toFixed(3)}</b></span>${seconds!==undefined?`<span>학습 <b>${Number(seconds).toFixed(1)}초</b></span>`:''}</div></article>`;
}
