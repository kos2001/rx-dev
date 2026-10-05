import {escapeHTML as esc} from './learning_cards.js';
const cases={
  drawer:{folder:'libero-drawer',label:'가운데 서랍 열기',title:'가운데 서랍을 열었어요.',description:'학습된 ACT 정책이 실제 MuJoCo 서랍을 여는 전체 기록입니다.',suiteLabel:'LIBERO-Goal',flow:['손잡이로 이동','손잡이를 잡고 당기기','열린 상태 확인']},
  basket:{folder:'libero-basket',label:'수프 통조림 바구니에 넣기',title:'물체를 집어 바구니에 넣었어요.',description:'수프 통조림을 잡고 들어 올린 뒤 바구니에 놓는 실제 정책 실행 기록입니다.',suiteLabel:'LIBERO-Object',flow:['통조림에 접근해 잡기','들어 올려 바구니로 이동','놓은 뒤 성공 판정 확인']}
};
export async function loadLiberoSuccess(){
  const root=document.getElementById('liberoSuccessGallery');
  const records={};
  const buttons=[...document.querySelectorAll('[data-libero-case]')];
  const results=await Promise.allSettled(Object.entries(cases).map(async([key,info])=>{
    const base='assets/success/'+info.folder+'/';
    const response=await fetch(base+'manifest.json');
    if(!response.ok)throw new Error('LIBERO recordings unavailable');
    return [key,{data:await response.json(),base,info}];
  }));
  for(const result of results){if(result.status==='fulfilled'){const [key,record]=result.value;records[key]=record;}}
  function show(key){
    const record=records[key];if(!record)return;
    const {data,base,info}=record;
    root.querySelectorAll('video').forEach(video=>video.pause());
    root.dataset.task=key;
    document.getElementById('liberoTaskTitle').textContent=info.title;
    document.getElementById('liberoTaskDescription').textContent='Apple M4 Mac · '+info.description;
    buttons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.liberoCase===key)));
    const runtime=data.runtime_policy_overrides;
    const imageSize=data.image_input?.width || 256;
    const rawImages=data.image_input?.raw_camera_images || false;
    root.innerHTML=`<div class="libero-summary"><div><span>실제 성공</span><strong>${data.successes} / ${data.episodes}<small>회</small></strong></div><div><span>확인한 과제</span><strong>${esc(info.label)}</strong></div><div><span>실행 조건</span><strong>Mac · ${data.step_limit}스텝</strong></div></div>
      <ol class="libero-action-flow" aria-label="${esc(info.label)} 행동 흐름">${info.flow.map((step,index)=>`<li><span>0${index+1}</span> ${esc(step)}</li>`).join('')}</ol>
      <div class="libero-recording-grid">${data.runs.map(run=>`<article class="libero-success-card"><video controls playsinline preload="metadata" poster="${base+esc(run.poster)}" aria-label="LIBERO ${esc(info.label)} ${run.success?'성공':'실패'} 영상 · Seed ${run.seed}"><source src="${base+esc(run.video)}" type="video/mp4"></video><div class="libero-recording-caption"><h3>초기 조건 ${run.init_state_index+1} <span class="badge ${run.final_success?'success':''}">${run.final_success?'최종 성공 유지':'최종 성공 없음'}</span></h3><p>Seed ${run.seed} · ${run.duration.toFixed(2)}초 · ${run.steps}스텝</p><p>최초 성공 ${run.first_success_step??'없음'}스텝 · 최고 보상 ${run.best_reward}</p><a href="${base+esc(run.video)}" download>전체 영상 다운로드 ↓</a></div></article>`).join('')}</div>
      <div class="libero-provenance"><p><strong>공개 사전학습 ACT · ${data.training_steps.toLocaleString()}스텝 학습 체크포인트</strong></p><p>이 Mac에서 추가 학습 없이 정책을 실행했습니다. LIBERO의 원래 성공 판정으로 확인하고, 성공 뒤에도 ${data.step_limit}스텝까지 기록했습니다. 이 결과는 한 과제의 ${data.episodes}개 초기 조건 사례이며 LIBERO 전체 성능을 뜻하지 않습니다.</p><p><a href="${esc(data.model_url)}" target="_blank" rel="noreferrer">모델 출처 ↗</a> · <a href="${base}manifest.json" target="_blank" rel="noreferrer">측정 기록과 버전 ↗</a></p><details><summary>전체 평가 조건과 원본 기록</summary><p>${esc(info.suiteLabel)} 과제 ${data.task_id} · 고정 초기 상태 ${data.initial_state_indices.join(', ')} · Seed ${data.runs.map(run=>run.seed).join(', ')} · n_action_steps=${runtime.n_action_steps}${runtime.temporal_ensemble_coeff?` · temporal_ensemble_coeff=${runtime.temporal_ensemble_coeff}`:''} · CPU 실행</p><p>학습 입력: 두 ${imageSize}×${imageSize} 카메라 영상 + 8차원 로봇 상태. 출력: 7차원 조작 행동. ${rawImages?'모델의 학습 조건에 따라 카메라 영상을 뒤집지 않고 입력합니다.':'공식 LIBERO 관측 처리에 따라 카메라 영상의 두 축을 뒤집어 입력합니다.'} 체크포인트의 정규화 통계를 사용합니다.</p><p>모델 버전 <code>${esc(data.model_revision)}</code></p><div class="table-scroll"><table><thead><tr><th>Seed</th><th>최초 성공</th><th>최종 성공</th><th>원본 행동·판정</th></tr></thead><tbody>${data.runs.map(run=>`<tr><td>${run.seed}</td><td>${run.first_success_step??'없음'}스텝</td><td>${run.final_success?'유지':'없음'}</td><td><a href="${base+esc(run.trace)}" download>기록 다운로드</a></td></tr>`).join('')}</tbody></table></div></details></div>`;
  }
  buttons.forEach(button=>{
    button.disabled=!records[button.dataset.liberoCase];
    button.onclick=()=>show(button.dataset.liberoCase);
  });
  const requested=new URLSearchParams(location.search).get('libero');
  show(records[requested]?requested:records.drawer?'drawer':Object.keys(records)[0]);
  if(!Object.keys(records).length)root.textContent='LIBERO 실행 기록을 불러올 수 없습니다. 새로고침해 주세요.';
}
