import {escapeHTML as esc} from './learning_cards.js';
export async function loadLiberoSuccess(){
  const root=document.getElementById('liberoSuccessGallery');
  const base='assets/success/libero-drawer/';
  try{
    const response=await fetch(base+'manifest.json');
    if(!response.ok)throw new Error('LIBERO recordings unavailable');
    const data=await response.json();
    root.innerHTML=`<div class="libero-summary"><div><span>실제 성공</span><strong>${data.successes} / ${data.episodes}<small>회</small></strong></div><div><span>확인한 과제</span><strong>가운데 서랍 열기</strong></div><div><span>실행 조건</span><strong>Mac · ${data.step_limit}스텝</strong></div></div>
      <ol class="libero-action-flow" aria-label="서랍 열기 행동 흐름"><li><span>01</span> 손잡이로 이동</li><li><span>02</span> 손잡이를 잡고 당기기</li><li><span>03</span> 열린 상태 확인</li></ol>
      <div class="libero-recording-grid">${data.runs.map(run=>`<article class="libero-success-card"><video controls playsinline preload="metadata" poster="${base+esc(run.poster)}" aria-label="LIBERO 서랍 열기 ${run.success?'성공':'실패'} 영상 · Seed ${run.seed}"><source src="${base+esc(run.video)}" type="video/mp4"></video><div class="libero-recording-caption"><h3>초기 조건 ${run.init_state_index+1} <span class="badge ${run.final_success?'success':''}">${run.final_success?'최종 성공 유지':'최종 성공 없음'}</span></h3><p>Seed ${run.seed} · ${run.duration.toFixed(2)}초 · ${run.steps}스텝</p><p>최초 성공 ${run.first_success_step??'없음'}스텝 · 최고 보상 ${run.best_reward}</p><a href="${base+esc(run.video)}" download>전체 영상 다운로드 ↓</a></div></article>`).join('')}</div>
      <div class="libero-provenance"><p><strong>공개 사전학습 ACT · ${data.training_steps.toLocaleString()}스텝 학습 체크포인트</strong></p><p>이 Mac에서 추가 학습 없이 정책을 실행했습니다. LIBERO의 원래 성공 판정으로 확인하고, 성공 뒤에도 300스텝까지 기록했습니다. 이 결과는 한 과제의 세 초기 조건 사례이며 LIBERO 전체 성능을 뜻하지 않습니다.</p><p><a href="${esc(data.model_url)}" target="_blank" rel="noreferrer">모델 출처 ↗</a> · <a href="${base}manifest.json" target="_blank" rel="noreferrer">측정 기록과 버전 ↗</a></p><details><summary>전체 평가 조건과 원본 기록</summary><p>LIBERO-Goal 과제 0 · 고정 초기 상태 0, 1, 2 · Seed ${data.runs.map(run=>run.seed).join(', ')} · n_action_steps=10 · CPU 실행</p><p>학습 입력: 두 카메라 영상 + 8차원 로봇 상태. 출력: 7차원 조작 행동. 공식 LIBERO 입력 전처리와 체크포인트 정규화 통계를 사용합니다.</p><p>모델 버전 <code>${esc(data.model_revision)}</code></p><div class="table-scroll"><table><thead><tr><th>Seed</th><th>최초 성공</th><th>최종 성공</th><th>원본 행동·판정</th></tr></thead><tbody>${data.runs.map(run=>`<tr><td>${run.seed}</td><td>${run.first_success_step??'없음'}스텝</td><td>${run.final_success?'유지':'없음'}</td><td><a href="${base+esc(run.trace)}" download>기록 다운로드</a></td></tr>`).join('')}</tbody></table></div></details></div>`;
  }catch(error){root.textContent='LIBERO 실행 기록을 불러올 수 없습니다. 새로고침해 주세요.';}
}
