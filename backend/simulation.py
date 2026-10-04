"""Run LeRobot's ALOHA and PushT simulations and save local videos."""
import argparse
import json
from importlib.metadata import version
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch
from lerobot.envs.configs import AlohaEnv, PushtEnv
from lerobot.envs.factory import make_env


def run(config, steps, output=Path("outputs"), name=None):
    env = make_env(config, n_envs=1)[config.type][0]
    rewards = []
    frames = 0
    name = name or config.type
    try:
        observation, _ = env.reset(seed=42)
        env.action_space.seed(42)
        path = output / f"{name}.mp4"
        with imageio.get_writer(path, fps=config.fps) as writer:
            for step in range(steps):
                if config.type == "aloha":
                    action = observation["agent_pos"].copy()
                    action[:, [0, 7]] += 0.04 * np.sin(step / 20)
                    action[:, [1, 8]] += 0.02 * np.cos(step / 20)
                    action[:, [6, 13]] = 0.5 + 0.4 * np.sin(step / 25)
                else:
                    action = np.array([[256 + 150 * np.cos(step / 15),
                                        256 + 150 * np.sin(step / 15)]], dtype=np.float32)
                observation, reward, terminated, truncated, _ = env.step(action)
                frame = env.call("render")[0]
                writer.append_data(frame)
                if step == 0:
                    imageio.imwrite(path.with_suffix(".png"), frame)
                rewards.append(float(reward[0]))
                frames += 1
        return {"environment": config.gym_id, "steps": frames,
                "max_reward": max(rewards), "video": str(path),
                "controller": "scripted motion, no trained policy", "name": name}
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=["all", "pusht", "aloha", "transfer"], default="all")
    parser.add_argument("--steps", type=int)
    parser.add_argument("--output", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    if args.steps is not None and args.steps < 1:
        parser.error("--steps must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    runs = []
    if args.environment in ["all", "aloha"]:
        runs.append(run(AlohaEnv(), args.steps or 250, args.output))
    if args.environment == "transfer":
        runs.append(run(AlohaEnv(task="AlohaTransferCube-v0"), args.steps or 250, args.output, "transfer"))
    if args.environment in ["all", "pusht"]:
        runs.append(run(PushtEnv(), args.steps or 100, args.output))
    results = {
        "lerobot": version("lerobot"),
        "torch": torch.__version__,
        "mps_available": torch.backends.mps.is_available(),
        "runs": runs,
    }
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
