// Concept diagrams describe algorithms; all measured results remain in the record cards.
const lessons={
  act:{name:'ACT',type:'모방학습',question:'여러 행동을 한 묶음으로 예측해요.',description:'시연에서 현재 관측과 이어지는 행동 묶음을 배웁니다. 실행할 때 다음 행동들을 함께 예측해 로봇을 움직입니다.',steps:['시연의 관측','행동 묶음 예측','시연 행동과 비교'],note:'학습 loss는 시연을 맞추는 정도입니다. 실제 과제 성공은 시뮬레이터 평가에서 확인하세요.'},
  diffusion:{name:'Diffusion Policy',type:'모방학습',question:'잡음에서 행동을 조금씩 만들어 가요.',description:'시연으로 학습한 모델이 현재 관측을 바탕으로 잡음을 단계적으로 줄여 행동 시퀀스를 생성합니다.',steps:['관측 + 초기 잡음','잡음 단계적 제거','행동 시퀀스 생성'],note:'반복 생성 과정이 행동을 만듭니다. 평가할 때 Seed와 실행 조건을 함께 기록하세요.'},
  ppo:{name:'PPO',type:'강화학습',question:'새 경험을 모으고 조금씩 업데이트해요.',description:'현재 정책으로 환경 경험을 수집한 뒤, 정책 변화가 지나치게 커지지 않도록 제한하며 보상을 높이는 방향으로 학습합니다.',steps:['현재 정책 실행','경험과 보상 수집','변화 제한 업데이트'],note:'경험 수집 간격은 한 번에 모을 환경 스텝 수입니다. 높은 보상과 과제 성공은 함께 확인하세요.'},
  sac:{name:'SAC',type:'강화학습',question:'경험을 다시 쓰며 다양한 행동을 탐색해요.',description:'저장한 경험을 학습에 재사용하며, 보상과 행동의 다양성을 함께 고려합니다. 연속적인 로봇 행동을 학습하는 방법입니다.',steps:['다양한 행동 탐색','경험 저장·재사용','보상 + 다양성 학습'],note:'탐색도 학습의 일부입니다. 짧은 실행은 연결 확인에 도움이 되지만 성능 검증에는 충분한 평가가 필요합니다.'}
};
export function renderMethodLesson(method,blocked=false){
  const lesson=lessons[method];if(!lesson)return;
  const container=document.getElementById('methodLessonContent');
  document.getElementById('trainingConfiguration').dataset.method=method;
  document.querySelectorAll('[data-lesson-method]').forEach(button=>{
    button.setAttribute('aria-pressed',String(button.dataset.lessonMethod===method));button.disabled=blocked;
  });
  if(container.dataset.method===method)return;
  container.dataset.method=method;
  container.innerHTML=`<div class="lesson-copy"><span class="path-label">${lesson.type} · ${lesson.name}</span><h3>${lesson.question}</h3><p>${lesson.description}</p></div><ol class="method-diagram" aria-label="${lesson.name} 개념 흐름">${lesson.steps.map((step,index)=>`<li><span>0${index+1}</span><strong>${step}</strong></li>`).join('')}</ol><p class="method-note">${lesson.note}</p>`;
}

// Prerequisites and unfinished service adapters are distinct from executable examples.
export const environmentGuides={
  libero:{label:'학습·평가 실행기 연결 필요',status:'Mac 구동 확인 · 학습 미연결',demo:'assets/probes/libero/rollout.mp4',setup:'공식 LeRobot 연동은 Linux 전용입니다. 별도 가상환경에서 Linux EGL 탐색 의존성을 제외한 hf-libero 0.1.4는 Apple M4 Mac에서 과제 초기화·60스텝·카메라 영상 저장을 확인했습니다.',connection:'이번 확인은 시뮬레이터 구동 테스트입니다. 학습된 정책의 과제 성공은 아닙니다. 과제 선택, 카메라·상태 입력, 7차원 행동, 성공 판정을 서비스의 학습·평가 실행기에 연결해야 합니다.'},
  leisaac:{label:'GPU 실행기 연결 필요',status:'macOS 설치 불가 · 원격 GPU 필요',setup:'NVIDIA GPU 머신 또는 GPU 클라우드에 Isaac Sim·Isaac Lab·LeIsaac와 호환 CUDA 환경을 준비합니다.',connection:'시뮬레이터 작업을 실행할 서버와 과제·관측·행동 설정을 연결하고, 실행 지표·영상을 이 화면으로 가져와야 합니다.'},
  envhub:{label:'Hub 환경 실행기 구현 필요',setup:'CartPole Hub 환경 코드를 검토하고 버전을 고정한 뒤 필요한 Gymnasium 의존성을 준비합니다.',connection:'Hub 환경 로더, 관측·행동 형식, 학습·평가 실행과 영상 저장을 연결해야 합니다. CartPole의 이산 행동을 현재 PPO·SAC 실행기가 그대로 지원하는 것은 아닙니다.'},
  metaworld:{label:'과제 실행기 연결 필요',setup:'LeRobot의 Meta-World 추가 패키지와 MuJoCo 환경을 준비합니다.',connection:'과제 선택, 정책 입출력과 성공 판정, 학습·평가 및 영상 저장을 서비스에 연결해야 합니다.'}
};
