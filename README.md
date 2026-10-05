# Robot Lab · 로봇 학습과 Agent 솔루션 플랫폼

로봇 정책 학습, 시뮬레이터 평가, Agent를 통한 실험 개선을 연결하는 로컬 플랫폼입니다.
플랫폼 홈에서 모방·강화학습, Agent 실험 설계, 정책 검증 솔루션으로 이동하고
실제 MuJoCo 성공 사례와 전체 평가 결과를 확인할 수 있습니다.
학습 워크스페이스는 학습 → 평가 → Agent 실험 → 기록·재개의 흐름으로 구성합니다.
Hermes `rx-dev` 프로필의 분석·설계·검토 역할은 실험 근거를 읽고 설정 후보를
실제 시뮬레이터에서 비교합니다. 실시간 제어에는 LLM을 호출하지 않습니다.

## 실행

```sh
sh run_app.sh
```

프론트엔드는 http://127.0.0.1:3030, 백엔드는 http://127.0.0.1:8787입니다.
먼저 `uv`와 `python3`를 설치합니다. Python 3.12 환경과 LeRobot 의존성은
`run_simulation.sh`가 준비합니다. 현재 실행 스크립트는 macOS의 `/private/tmp`를 사용합니다.
Hermes 연결 없이도 로컬 학습과 평가를 실행할 수 있습니다.
대시보드에서 완료된 PushT 기록을 선택하고 **Agent 개선 실험**을 누릅니다.
대시보드의 제어기 Agent는 PushT를 대상으로 합니다. 모델 학습 화면에서는
MuJoCo ALOHA의 학습·평가와 학습 Agent 실험도 실행할 수 있습니다.

새 실행 결과·모델 가중치·데이터 캐시와 인증 정보는 저장소에 포함하지 않습니다.
대시보드의 성공 사례 영상 2개·비교용 실패 영상 1개와 출처·측정 메타데이터는
`frontend/assets/success/`에 포함합니다. 이 영상들은 백엔드나 로컬 `outputs/` 없이도 재생됩니다.
README의 과거 실행 ID와 결과 경로는 개발 환경의 검증 기록이며 새로 받은 코드에는 없습니다.
`outputs/`의 기록은 직접 학습·평가를 실행하면 생성됩니다.

## 교육용 시각화

학습(파랑)·평가(주황)·Agent(보라)·기록과 재개(청록)를 색상과 제목으로 함께 구분합니다.
모방·강화학습의 입력과 학습 흐름을 개념도로 설명하며, ACT·Diffusion·PPO·SAC 선택 시
설명과 실제 학습 설정이 함께 바뀝니다. 방법 선택만으로 학습을 실행하지 않습니다.
성공률·보상·95% 구간의 뜻과 Agent 분석·설계·검토, 개발·최종 평가의 차이를 안내합니다.
교육용 예시는 설명에만 사용하고 결과 카드는 실제 측정값을 유지합니다.

## 학습 & Agents 카드 워크스페이스

학습 설정은 정책·환경, 학습 신호·모델, 실행 예산 카드로 나눕니다. 정책 평가 카드에서는
실제 성공 수·성공률·최고 보상과 영상을 확인하고, 전체 평가 비교표를 펼칠 수 있습니다.
Agent 영역은 분석·설계·검토 역할 카드와 기준·후보 비교 카드로 구성하며,
별도 최종 평가가 있으면 측정된 성공률 구간과 반례도 함께 표시합니다.
실행 기록은 종류 필터·방법/환경/ID 검색·더보기로 탐색하고 카드 안에서 체크포인트와
로그·영상을 확인합니다. `tests/browser_learning_cards.cjs`는 실제 기록을 읽어 표시값과
재생 유지·검색·필터·모바일 배치를 검증하고, 폼 제출은 요청을 가로채 실행 값만 검사합니다.

## macOS LIBERO 구동 검증

Apple M4 · macOS 26.7에서 LIBERO-Spatial 과제 0의 초기화, 60스텝 실행과
카메라 영상 저장을 확인했습니다. 학습된 정책을 사용하지 않았으며 과제 성공은 없습니다.
공식 LeRobot LIBERO extra는 여전히 Linux 전용입니다. 실험용 별도 가상환경에서
Linux EGL 장치 탐색 패키지 `egl-probe`·`hf-egl-probe`를 제외하고 robosuite의
macOS 렌더링 경로를 사용했습니다. `requirements/libero-macos.txt`는 실제 구동된
패키지를 고정하며 `--no-deps` 설치는 이 검증 전용입니다. 메인 학습 환경에 적용하지 않습니다.

```sh
sh run_libero_probe.sh --steps 60
```

최초 실행은 고정된 `lerobot/libero-assets` 자산 약 422MB를 다운로드합니다.
`outputs/platform-probes/libero-macos/`에 영상·원본 trace·버전·결과를 저장합니다.
서비스 환경 카드에서도 `frontend/assets/probes/libero/`의 실제 구동 영상을 확인할 수 있습니다.
이 검증은 전체 과제 지원이나 서비스의 LIBERO 학습·평가 연결을 뜻하지 않습니다.

Isaac Sim 6.1.0.0 설치 해석도 확인했습니다. macOS ARM64 배포 파일이 없어
설치할 수 없으며, LeIsaac의 실행에는 지원되는 GPU PC·서버 연결이 필요합니다.
GPU 서버 주소·접속 설정이 제공되지 않아 원격 실행은 수행하지 않았습니다.

## 여러 방식의 모델 학습과 평가

### 실제로 성공하는 사전학습 정책 실행

공개 모델 `lerobot/act_aloha_sim_transfer_cube_human`을 가져와 로컬 MuJoCo에서
Cube transfer를 실행할 수 있습니다. 이 모델은 공개된 80,000스텝 학습 체크포인트이며,
이 프로젝트에서 짧게 학습한 PPO 모델과 별개입니다. 모델 저장소의 설명과 원자료를
참조하세요: https://huggingface.co/lerobot/act_aloha_sim_transfer_cube_human

```sh
HF_HOME="$PWD/outputs/hf-cache" TORCH_HOME="$PWD/outputs/torch-cache" \
  /private/tmp/rx-dev-lerobot-venv/bin/python -m lerobot.processor.migrate_policy_normalization \
  --pretrained-path lerobot/act_aloha_sim_transfer_cube_human \
  --revision ba73b2766f1371cdc133ca4efb97eb090d744625 \
  --output-dir outputs/pretrained/act_aloha_transfer_migrated

/private/tmp/rx-dev-lerobot-venv/bin/python -m backend.pretrained_success \
  --model outputs/pretrained/act_aloha_transfer_migrated \
  --output outputs/pretrained-transfer-NEW --full-rollout
```

LeRobot의 공식 마이그레이션 도구로 정규화 통계를 processor에 옮깁니다.
모델의 학습 가중치는 다시 학습하지 않습니다. `--full-rollout`은 최초 공식 성공 후에도
400스텝까지 실제 물리 시뮬레이션을 이어서 녹화하며, 최초 성공과 최종 성공을 별도로 기록합니다.
2026-10-05 실제 실행에서는 사전에 정한 Seed 42000·42001이 성공했고 42002는 실패했습니다.
성공한 두 실행은 보상 4에 도달하고 400스텝 종료 시점까지 성공 상태를 유지했습니다.
세 영상과 전체 reward trace를 보존했습니다. 3개 초기 조건은 일반화 성능 벤치마크가 아닙니다.

대시보드의 사전학습 ACT 기록을 선택하면 모든 실행 영상을 볼 수 있습니다.
`?report=<실행 ID>` 링크로 특정 기록을 바로 열 수 있습니다.
대시보드 첫 화면의 **학습된 행동을, 실제 실행으로** 영역에서는 포함된 성공 영상을
바로 재생하고 다운로드할 수 있습니다. **전체 평가 결과**를 펼치면 성공 2/3의 측정 표와
실패 영상도 확인할 수 있습니다. `tests/browser_showcase.cjs`는 백엔드 연결을 차단한
상태에서 이 재생·다운로드·전체 결과·모바일 레이아웃을 검증합니다.

왼쪽 **학습 & Agents** 메뉴에서 학습 방법과 실행 방식을 선택합니다.
모방학습은 LeRobot 0.6.1 학습기를, 강화학습은 Stable Baselines3 2.9.0과
gym-pusht와 MuJoCo 기반 gym-aloha 시뮬레이터를 사용합니다.

| 방법 | 학습 신호 | 입력 | 스텝의 의미 |
| --- | --- | --- | --- |
| ACT | 시연 행동과 예측의 오차 | 영상 + 로봇 위치 | 가중치 업데이트 |
| Diffusion Policy | 시연 행동의 확산·복원 오차 | 영상 + 로봇 위치 | 가중치 업데이트 |
| PPO | 새 경험의 환경 보상 | 물체·로봇 위치와 각도 | 수집할 환경 스텝 |
| SAC | 경험 버퍼의 환경 보상 | 물체·로봇 위치와 각도 | 수집할 환경 스텝 |

ACT/Diffusion은 기본 `lerobot/pusht` 또는 다른 LeRobot 형식의 Hub 데이터셋에서
처음 N개 시연 에피소드를 사용합니다. `compact` 모델 크기는 로컬 실험용입니다.
ACT는 hidden dimension 128, feedforward 512, encoder/VAE encoder 각 2층,
행동 묶음 16으로 줄입니다. Diffusion은 U-Net 채널 128/256/512, horizon 16,
행동 실행 길이 8로 줄입니다. `standard`는 각 정책의 공식 기본 구조를 사용합니다.
두 크기는 서로 다른 모델이며 결과에 설정이 함께 저장됩니다.

PPO/SAC는 데이터셋을 받지 않고 선택한 환경에서 경험을 직접 수집합니다.
PushT에서는 `gym_pusht/PushT-v0`를 사용합니다.
한 에피소드의 최대 길이는 300스텝이며 PushT 보상은 환경의 원래 겹침 보상입니다.
MLP 정책에는 정규화한 네 위치 좌표와 각도의 sin/cos를 제공합니다.
행동은 [-1, 1]에서 환경의 [0, 512] 목표 좌표로 변환합니다.
이 방식은 물체 위치를 직접 알고 있으므로 영상 입력 모방학습과 같은 조건의 비교가 아닙니다.
PPO는 경험 수집 간격과 배치 크기를, PPO/SAC는 학습률과 보상 할인율을 설정할 수 있습니다.
PPO 수집 스텝은 간격의 배수, 간격은 배치 크기의 배수여야 합니다.
SAC는 초기 32스텝 뒤 매 스텝 1회 갱신하며 경험 버퍼 크기는 100,000입니다.

실행 방식:

- **새 모델 학습**: 선택한 방법으로 새로운 정책을 학습합니다.
- **저장 모델 미세조정**: ACT/Diffusion 가중치와 구조를 가져와 새 optimizer로 학습합니다.
  데이터셋을 바꿀 수 있지만 기존 모델과 관측·행동 feature가 호환되어야 합니다.
- **체크포인트에서 이어 학습**: ACT/Diffusion은 가중치·optimizer·scheduler·스텝을 복원합니다.
  스텝 입력은 재개 후의 총 목표이며 원래 데이터셋, 에피소드, 배치, Seed를 유지합니다.
  PPO/SAC는 정책과 optimizer를 불러오고 입력한 수만큼 환경 스텝을 추가합니다.
  SAC는 저장된 경험 버퍼도 복원합니다. 환경 상태와 모든 난수 상태를 그대로 복원하는
  비트 단위 재현을 보장하지 않습니다. 설정은 원래 실행의 값을 유지합니다.

기본 장치는 CPU입니다. MPS/CUDA는 해당 장치가 실제로 사용 가능한 환경에서
선택할 수 있습니다. 학습·정책 평가·기존 시뮬레이션·Agent 실험은 동시에 실행하지 않습니다.
설정, 로그, 상태는 `outputs/training/<id>/`에 보존하며, 중지하거나 서버가 재시작돼도
완료된 원본 기록은 덮어쓰지 않습니다. 중지 시 마지막 저장 이후의 작업은 유실될 수 있습니다.

ACT/Diffusion 가중치와 processor는 `model/checkpoints/<step>/pretrained_model/`,
optimizer 등은 해당 checkpoint의 `training_state/`에 저장합니다.
PPO/SAC는 `model/policy.zip`, SAC 경험 버퍼는 `model/replay_buffer.pkl`에 저장합니다.
학습은 1,000스텝마다 및 마지막 스텝에 저장합니다. SAC의 경험 버퍼는 정상 완료 시 저장하므로
중간 중지 후 이어 학습하려면 완료된 SAC 기록을 선택해야 합니다.

학습 환경은 PushT와 MuJoCo ALOHA의 두 작업을 지원합니다. 세 환경 모두
ACT·Diffusion·PPO·SAC 학습과 정책 평가, Agent 학습 실험으로 연결됩니다.

| 환경 선택 | 물리 엔진 | ACT/Diffusion 시연 데이터 |
| --- | --- | --- |
| PushT | Pymunk | `lerobot/pusht` |
| ALOHA · Peg insertion | MuJoCo | `lerobot/aloha_sim_insertion_scripted` |
| ALOHA · Cube transfer | MuJoCo | `lerobot/aloha_sim_transfer_cube_scripted` |

환경을 선택하면 시연 데이터 기본값이 바뀝니다. 공식 데이터와 다른 작업의 조합,
다른 환경의 체크포인트 재개는 거부합니다. 일반 학습 API는 `environment`에
`pusht`·`aloha`·`transfer`를 받습니다. 평가와 Agent 실험은 원본 기록의 환경을 유지합니다.
기존 PushT 기록은 환경 필드 없이도 사용할 수 있습니다.

ALOHA 모방학습은 top 카메라와 14차원 관절 상태를 사용합니다.
ALOHA 강화학습은 관절·물체 자세·속도의 privileged simulator state를 사용합니다.
행동은 스텝당 최대 0.08라디안의 관절 목표 변화와 두 gripper의 0–1 목표입니다.
MuJoCo의 기본 단계 보상 0–4를 그대로 사용하고 성공은 공식 `is_success`/보상 4입니다.
영상 모델과 상태 모델의 성능을 같은 입력 조건으로 취급하지 않습니다.
희소 보상 환경에서 짧은 학습은 연결 확인용이며 작업 성공을 보장하지 않습니다.
macOS에서는 MuJoCo 렌더링에 그래픽 서비스 접근이 필요합니다.

MuJoCo 연결 검증에서는 Peg insertion·Cube transfer의 네 방법, 총 8개 정책을
실제로 학습하고 각 정책의 10스텝 평가·영상 재생을 확인했습니다. ACT 학습 재개는
두 환경 모두 확인했습니다. PPO는 128 환경 스텝에서 10회, SAC는 64 환경 스텝에서
32회의 gradient update를 기록했습니다. 결과는 `outputs/mujoco-learning-verification.json`입니다.
모든 짧은 평가의 성공률은 0이며 성능 벤치마크로 해석하면 안 됩니다.
PPO/SAC의 저장 모델 재개도 두 환경에서 확인했습니다. PPO는 누적 256스텝·20회
갱신, SAC는 누적 128스텝·96회 갱신을 기록했습니다.
`outputs/mujoco-continuation-verification.json`에 원본·재개 기록 ID를 보존했습니다.

2026-10-05 MuJoCo Hermes 전체 연결 검증: 실험 `30cf44aee71f4d9fbe9bf81ca02d559c`에서
Peg insertion PPO의 배치 크기 8→16을 비교했습니다. 두 정책을 같은 학습 Seed
500001로 각각 128 환경 스텝 학습하고, 새 Seed 40001에서 각각 10스텝 평가했습니다.
분석·설계·검토 역할과 적용 스킬, 실제 학습·평가, 데스크톱·모바일 표시가 통과했습니다.
두 정책 모두 성공 0/1·최고 보상 0으로 실제 검토 판정은 `inconclusive`입니다.
영상은 `outputs/training/36f9988cbb37465caf470903b05b3b6e/evaluation/seed-40001.mp4`
(기준)와 `outputs/training/9c0a190ba3e9431891f5e0c66853d50c/evaluation/seed-40001.mp4`
(후보)에 저장했습니다.

학습 기록의 **정책 평가** 버튼은 기록에 저장된 환경에서 학습된 정책을 실행합니다.
ACT/Diffusion은 아래의 환경별 공식 시연 데이터로 학습한 기록을 평가할 수 있습니다.
평가 에피소드 수(1–20), 최대 스텝(10–300), 연산 장치를 선택합니다.
Seed 20000부터 같은 초기 조건에서 실행하며 성공률, 평균 최고 보상, 영상과 원자료를
`evaluation/`에 저장합니다. LeRobot 평가는 처음 최대 10개, PPO/SAC는 전체 에피소드를 녹화합니다.
같은 입력, Seed, 에피소드 수, 스텝 제한의 결과끼리 비교해야 합니다.
평가 조건을 재사용하며 튜닝했다면 최종 성능을 주장하기 전에 별도 초기 조건의 평가가 필요합니다.

데이터셋과 영상 인코더 캐시는 `outputs/hf-cache/`, `outputs/torch-cache/`에 둡니다.
Hub 업로드와 W&B 로깅은 비활성화합니다. 직접 시연 수집, VLA 학습과
LeRobot HIL-SERL의 인간 개입 강화학습은 현재 UI 범위에 포함하지 않습니다.
기존 MP4/trace JSON을 시연 데이터셋으로 자동 변환하는 기능도 아직 없습니다.

API:
`GET /api/training/methods`, `GET /api/training`, `GET /api/training/current`,
`POST /api/training`, `POST /api/training/evaluate`, `POST /api/training/stop` (`{}`).

```json
{"algorithm":"diffusion","mode":"new","preset":"compact","dataset":"lerobot/pusht","device":"cpu","steps":1000,"batch_size":8,"episodes":10,"seed":1000}
```

```json
{"algorithm":"ppo","mode":"new","device":"cpu","steps":1024,"batch_size":8,"rollout_steps":128,"learning_rate":0.0003,"gamma":0.99,"seed":1000}
```

```json
{"source_job":"학습 기록의 32자리 ID","device":"cpu","episodes":5,"step_limit":300}
```

공식 참고: [LeRobot 학습](https://huggingface.co/docs/lerobot/main/il_sim),
[PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html),
[SAC](https://stable-baselines3.readthedocs.io/en/master/modules/sac.html).

2026-10-04 검증에서 ACT/Diffusion의 새 학습·재개·미세조정·평가와
PPO/SAC의 새 학습·추가 학습·평가, 총 14번의 실제 실행을 확인했습니다.
강화학습은 실제 gradient update가 발생했는지 검사했습니다.
원자료: `outputs/learning-validation-20261004/verification.json`.
이는 기능 확인이며 학습 성능의 벤치마크가 아닙니다. 새 디렉터리에서 재검증하려면:

```sh
/private/tmp/rx-dev-lerobot-venv/bin/python -m scripts.verify_training_methods --output outputs/learning-validation-NEW
```

## Hermes 설정

이 Mac에는 다음 매핑을 설치했습니다.

```text
frontend :3030 → backend :8787 → Hermes gateway :8700
                              → upstream rx-dev :8679 → Hermes Agent Engine
```

공유 게이트웨이에는 upstream `rx-dev`와 model alias `rx-dev` → `rx-dev/rx-dev`가
등록됩니다. 모든 실행과 조회에 `X-Hermes-Upstream: rx-dev`를 명시합니다.
역할마다 별도 세션과 실제 Hermes run ID가 있어 서로의 대화 기록을 공유하지 않습니다.
설치된 Hermes의 per-profile 서비스 구조를 유지하며 다른 프로필은 변경하지 않습니다.

새로 구성할 때는 **설치된 Hermes 가상환경 Python**으로 실행합니다.

```sh
"${HOME}/.hermes/hermes-agent/venv/bin/python" scripts/setup_hermes.py \
  --gateway-env /path/to/shared-gateway/.env \
  --source-profile default --start
```

설치 스크립트는 전용 프로필/API 키를 만들고 기존 공유 게이트웨이 경로·키·기본 경로를
보존합니다. 변경 전 설정과 `.env`는 원래 디렉터리에 권한 600으로 백업합니다.
`--start`는 이 Mac의 launchd 서비스와 공유 게이트웨이 재시작을 포함하므로
다른 프로젝트가 긴 작업을 실행 중이면 재시작 시점을 조율해야 합니다.

키는 `~/.hermes/profiles/rx-dev/.env`에만 저장되며 브라우저에 전달하지 않습니다.
백엔드는 이 파일을 읽습니다. 필요하면 `RX_DEV_HERMES_ENV`,
`RX_DEV_GATEWAY_BASE_URL`, `RX_DEV_GATEWAY_KEY` 환경변수로 바꿀 수 있습니다.
게이트웨이 주소는 로컬 loopback만 허용합니다.

## Agent 실행 범위와 결과

1. 분석 Agent가 전체 trace에서 계산한 무접촉·정체 구간, 공식 성공 기준과 실패 상태 샘플을 검토합니다.
2. 설계 Agent가 과거 실험 이력을 읽고, 허용 범위 내 설정을 정확히 한 가지 변경합니다. 이미 평가한 후보는 거부합니다.
3. 백엔드가 설정의 키·타입·계산량 범위를 검사하고, 기존 설정과 후보를 동일한 새 Seed 10개에서 실행합니다.
4. 별도 검증 Agent가 실제 측정 결과와 한계를 검토합니다.

실험은 한 번에 하나만 실행하며, Agent와 일반 시뮬레이션도 동시에 실행하지 않습니다.
새 Seed는 기존 평가, 과거 Agent 실험과 별도 제어기 연구의 Seed를 제외합니다.
새 실험은 초기 조건 Seed와 탐색 Seed를 분리하며 탐색 난수를 12345로 고정합니다.
성공률의 95% Wilson 구간도 저장합니다. 성공 수가 증가하면
`improved`, 감소하면 `regressed`, 동일하면 `inconclusive`로 표시합니다.
이는 단일 개발 실험의 판정이며 통계적 유의성이나 일반화를 보장하지 않습니다.
후보를 기본 제어기로 자동 채택하지 않고 원래 결과도 덮어쓰지 않습니다.

Agent의 터미널·파일·외부 서비스 도구는 비활성화했습니다. 수치 데이터와 일부 상태
기록은 Hermes에 설정된 모델 제공자에게 전달되며, 원본 영상은 로컬에 남습니다.
현재 실제 로봇 연결이나 배포 승인 기능은 없습니다.

`outputs/agents/<job-id>/`에 입력 근거, 역할별 출력과 run ID, 설정 요청,
시뮬레이터 로그, paired 평가 결과를 저장합니다. 실행 중 UI에서 중지할 수 있습니다.
네트워크 조회 오류 시 같은 run ID를 재조회하며 중복 실행하지 않습니다.
출력 검증에서 거부된 Agent 응답은 `rejected_<역할>.json`으로 작업 폴더에만 남기며 API로 노출하지 않습니다.
백엔드 재시작으로 중단된 작업은 자동 재실행하지 않고 저장된 run ID를 남깁니다.

## 역할별 스킬과 제어기 개선

`skills/`의 분석·실험 설계·평가 검토 스킬은 각 역할의 실제 실행 지침에 포함됩니다.
설계는 단일 변수 변경, 실패 이력 재사용, 새 평가 조건 확보를 강제하고,
검토는 백엔드 성공 수와 일치하는 판정만 허용합니다. 설치본을 갱신하려면:

```sh
python3 scripts/install_rx_dev_skills.py
```

이는 Codex 스킬과 전용 Hermes rx-dev 프로필의 제어기 스킬 세 개와 학습 스킬 세 개를 갱신합니다.
LLM의 자유 서술은 여전히 수치 오인 가능성이 있으므로 측정 표와 저장된 JSON을 우선합니다.

## 모델 학습과 Agent·스킬 연결

모델 학습 화면의 **Agent 학습 실험 시작**은 완료된 PushT 또는 MuJoCo ALOHA 학습 기록을 분석 근거로 사용합니다.
`rx-dev-learning-analysis` → `rx-dev-learning-design` → 로컬 학습·평가 →
`rx-dev-learning-review` 순서로 실행하며, 각 역할에는 저장소의 해당 `SKILL.md`를 직접 포함합니다.
스킬 설치 없이도 역할 실행에 적용됩니다. Hermes 모델 연결이 필요하며 수치 학습 곡선,
설정과 평가 지표를 연결된 모델 제공자에 전달합니다. 원본 영상과 원시 학습 로그는 전달하지 않습니다.

설계 Agent는 같은 알고리즘에서 배치 크기·학습 스텝, 또는 강화학습의 학습률·할인율 중
하나만 변경합니다. 백엔드는 범위·PPO 배수·중복 제안 여부를 검사합니다.
원본 체크포인트를 변경하지 않고 기준·후보 모두 작은 모델을 **새로 학습**합니다.
같은 초기화 Seed와 새로운 동일 평가 Seed를 사용합니다. 학습량이나 배치 크기를 바꾸면
연산량도 달라질 수 있으며, 모델 성능 개선이 보장되지 않습니다.

정책당 상한은 ACT/Diffusion 1–512 업데이트, PPO 128–2048 환경 스텝(128의 배수),
SAC 64–2048 환경 스텝입니다. 정책당 평가 1–5개, 에피소드당 10–300스텝을 허용합니다.
화면에 역할·스킬·Hermes run ID, 하위 학습·평가 ID와 성공 수·보상·학습 시간을 표시합니다.
체크포인트·로그·영상은 학습 기록에서 확인할 수 있습니다. 성공 수가 같으면 판정은
`inconclusive`이며, 적은 표본과 한 학습 Seed로 통계적 개선이나 일반화를 주장하지 않습니다.
자동 채택이나 반복 탐색은 수행하지 않습니다.

API: `POST /api/learning-agents`, `GET /api/learning-agents/current`,
`POST /api/learning-agents/stop`. 결과는 `outputs/learning-agents/<id>/`에 보존합니다.
실험 중에는 수동 학습·평가·시뮬레이션을 시작할 수 없으며 Agent 중지 버튼으로 취소합니다.
`tests/browser_learning_agents.cjs`는 실제 Hermes 역할과 기준·후보 학습 및 평가를 실행하는
통합 검증입니다. 이 검증도 모델 제공자에 수치 데이터를 전달합니다.

2026-10-04 실제 연결 검증: 실험 `c31fc7665dbd4261863ae1c2049f7e36`에서
세 Hermes 역할을 독립 run으로 실행했습니다. ACT를 기준 배치 1·후보 배치 4로 각각
1업데이트 학습하고, 새 Seed 40000에서 각각 10스텝 평가했습니다. 두 정책 모두 성공
0/1, 최고 보상 0.095317로 검토 결과는 `inconclusive`였습니다. 이는 성능 벤치마크가
아닌 연결 확인입니다. 데스크톱·모바일 표시와 실험 중 수동 작업 차단도 검증했습니다.

실험용 제어기 v2는 실제 T자 표면을 겨냥해 재접촉하고, 목표 근처에서 짧게 밀며
예측된 공식 성공·겹침을 우선합니다. v1은 유지하여 기존 결과를 재현합니다.
`backend.improvement_study`는 개발 Seed 0–4에서 설정을 선택한 뒤, 별도 Seed
300–329에서 기존 v1과 선택된 v2를 동일 탐색 난수·300스텝으로 비교합니다.
완료된 비교는 `/api/controller-study`와 대시보드의 별도 표에서 확인합니다.
LLM 단일 설정 실험과 다른 연구이며 기본 제어기로 자동 승격하지 않습니다.
평가에 사용한 Seed는 이후 새 후보를 튜닝하는 데 재사용하지 않아야 합니다.

2026-10-04 완료된 비교: 기존 v1은 3/30(10%), v2/phase_steps=3은
13/30(43.3%) 성공했습니다. 성공으로 바뀐 쌍은 11개, 실패로 바뀐 쌍은 1개입니다.
평균 최종 보상은 0.724 → 0.734, 실행 시간은 6.18s → 7.58s였습니다.
시뮬레이터와 고정 탐색 난수에서의 결과이며 다중 탐색 난수·실물 로봇 성능은 미검증입니다.
원자료: `outputs/improvement-v2-terminal/test.json`. 완료된 연구 파일은 CLI가 덮어쓰지 않습니다.

## 후보 설정 비교 영상

완료된 평가를 같은 Seed와 설정으로 다시 녹화할 수 있습니다. 아래 명령의
`JOB_ID`는 `/api/agents/current`에서 확인한 작업 ID로 바꿉니다.

```sh
/private/tmp/rx-dev-lerobot-venv/bin/python -m backend.agent_recordings \
  --folder outputs/agents/JOB_ID
```

기존 설정과 후보를 각각 녹화해 Seed 10개당 MP4 20개와 상태 기록을 만듭니다.
성공 여부·스텝 수·보상·위치 및 각도 오차가 원래 평가와 일치해야 영상 목록을
게시합니다. 원래 평가 수치와 실행 시간은 덮어쓰지 않습니다.
영상은 `outputs/agents/JOB_ID/recordings/`, 목록은 `recordings.json`에 저장합니다.

대시보드 상단의 **Agent 후보 vs 기존 설정 · 실제 비교 영상**에서 Seed를 선택하고
**동시 재생** 또는 공통 시간 슬라이더를 사용합니다. 기본 선택은 한쪽만 성공한
대조 사례이며, 전체 Seed를 선택할 수 있습니다. 먼저 종료된 영상은 마지막 화면에
머뭅니다. 영상 프레임은 행동 직전 상태, 최종 보상과 성공은 행동 후 공식 측정값입니다.
아래 기존 평가 재생 영역은 원형 동작 대 MPC 비교이므로 이 후보 영상과 구분합니다.

## 검증

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
/private/tmp/rx-dev-lerobot-venv/bin/python -m unittest test_pusht_agent -v
```

`tests/browser_smoke.cjs`는 기존 대시보드와 실제 시뮬레이션 버튼을 검증합니다.
`tests/browser_agents.cjs`는 실제 Hermes 결과 화면, 모바일 너비, 브라우저에서
게이트웨이 직접 호출·인증키 노출이 없는지를 확인합니다. 로컬 서버와 Playwright가
필요하며 `EXPECT_COMPLETED=1`이면 세 역할과 실제 평가가 모두 완료돼야 통과합니다.
`tests/browser_recordings.cjs`는 후보 영상의 디코딩, 동시 재생, 공통 시간 이동,
Seed 선택과 모바일 화면을 실제 브라우저에서 검증합니다.
`tests/browser_training.cjs`는 실제 ACT 1스텝 학습과 체크포인트, 로그,
중지, 기록 유지, 모바일 화면을 검증합니다. 로컬 서버와 Playwright가 필요합니다.
`tests/browser_training_methods.cjs`는 네 방법의 실제 학습과 평가, 영상 디코딩,
ACT 재개와 모바일 화면을 확인합니다. `scripts.verify_training_methods.py`는
네 방법의 재개와 ACT/Diffusion 미세조정을 포함해 14개 실제 실행을 검증합니다.

Agent 상태 API: `/api/agents/health`, `/api/agents/current`.
실행: `POST /api/agents`에 `{"report_id":"agent"}`.
중지: `POST /api/agents/stop`에 `{}`. 임의 프롬프트나 명령 입력은 지원하지 않습니다.

### 실험 검증과 재개

VeriHarness의 불일치 검증·합의 반례 탐색과 Learn Harness Engineering의 상태 저장·검증 원칙을 학습 실험에 적용했습니다. 개발 평가 뒤 기준·후보 체크포인트를 고정하고, 별도 최종 Seed로 다시 평가합니다. 화면에서 최종 성공률 구간, 짝지은 검정, 퇴행·공통 실패 Seed, 성공 상태 유지 여부와 단계별 실행 기록을 확인할 수 있습니다. 중단된 실험은 **저장된 실험 재개** 버튼으로 이어갈 수 있습니다. 완료된 단계는 재사용하고 미완료 학습·평가는 같은 설정으로 처음부터 실행합니다.

이는 두 저장소의 원칙을 현재 서비스에 맞춰 구현한 것으로, 원본 런타임 전체를 설치한 것은 아닙니다. 작은 표본의 성공 수 증가를 최종 개선으로 단정하거나 모델을 자동 채택하지 않습니다. 설계·재개 조건과 검증 명령은 [실험 하네스 문서](docs/learning-harness.md)에 있습니다.
