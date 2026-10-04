"""Executable training methods and their input contracts."""
METHODS = [
    {"id": "act", "name": "ACT", "family": "imitation", "input": "영상 + 로봇 위치",
     "description": "시연 행동 묶음을 Transformer로 예측합니다.", "engine": "LeRobot"},
    {"id": "diffusion", "name": "Diffusion Policy", "family": "imitation", "input": "영상 + 로봇 위치",
     "description": "시연 행동의 분포를 확산 모델로 학습합니다.", "engine": "LeRobot"},
    {"id": "ppo", "name": "PPO", "family": "reinforcement", "input": "선택한 시뮬레이터의 물체·로봇 상태",
     "description": "현재 정책으로 새 경험을 수집하고 보상으로 정책을 갱신합니다.", "engine": "Stable Baselines3"},
    {"id": "sac", "name": "SAC", "family": "reinforcement", "input": "선택한 시뮬레이터의 물체·로봇 상태",
     "description": "경험 버퍼를 재사용하며 보상과 탐색을 함께 최적화합니다.", "engine": "Stable Baselines3"},
]
IMITATION = {"act", "diffusion"}
REINFORCEMENT = {"ppo", "sac"}
