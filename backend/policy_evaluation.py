"""Evaluate saved learning policies on identical seeded PushT episodes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from .training_methods import REINFORCEMENT
from .training_runner import check_device
from .learning_environments import ENVIRONMENTS, environment_of


def evaluate(config, checkpoint, output):
    check_device(config["device"])
    output.mkdir(parents=True)
    environment = environment_of(config)
    spec = ENVIRONMENTS[environment]
    if config["algorithm"] in REINFORCEMENT:
        metrics = evaluate_rl(config, checkpoint, output)
    else:
        policy_config = json.loads((checkpoint / "config.json").read_text())
        images = [feature["shape"] for feature in policy_config["input_features"].values()
                  if feature["type"] == "VISUAL"]
        if len(images) != 1:
            raise ValueError("Simulator evaluation requires a single image observation")
        height, width = images[0][-2:]
        command = [sys.executable, "-u", "-m", "lerobot.scripts.lerobot_eval",
                   f"--policy.path={checkpoint}", f"--policy.device={config['device']}",
                   f"--env.type={spec['type']}", f"--env.task={spec['task']}", f"--env.episode_length={config['step_limit']}",
                   f"--env.observation_height={height}", f"--env.observation_width={width}",
                   f"--eval.n_episodes={config['episodes']}", "--eval.batch_size=1",
                   f"--seed={config['seed']}", f"--output_dir={output}"]
        subprocess.run(command, check=True)
        raw = json.loads((output / "eval_info.json").read_text())
        aggregate = raw.get("overall", raw.get("aggregated"))
        if not aggregate:
            raise ValueError("Evaluator produced no aggregate metrics")
        metrics = {"episodes": config["episodes"], "success_rate": aggregate["pc_success"] / 100,
                   "mean_best_reward": aggregate["avg_max_reward"], "mean_sum_reward": aggregate["avg_sum_reward"],
                   "wall_seconds": aggregate["eval_s"], "raw_result": "eval_info.json"}
        tasks = raw.get("per_task", [])
        if len(tasks) != 1:
            raise ValueError("Paired evaluation requires exactly one task")
        episodes = tasks[0]["metrics"]
        metrics["runs"] = [{"seed": config["seed"] + index, "success": bool(success),
                            "best_reward": float(episodes["max_rewards"][index]),
                            "sum_reward": float(episodes["sum_rewards"][index])}
                           for index, success in enumerate(episodes["successes"])]
        if len(metrics["runs"]) != config["episodes"]:
            raise ValueError("Evaluator episode count differs from the requested paired sample")
    metrics.update(algorithm=config["algorithm"], environment=environment, simulator=spec, input=config["input"], source_job=config["source_job"],
                   seeds=list(range(config["seed"], config["seed"] + config["episodes"])), step_limit=config["step_limit"])
    temp = output / "metrics.tmp"
    temp.write_text(json.dumps(metrics, indent=2, allow_nan=False))
    temp.replace(output / "metrics.json")
    print(json.dumps(metrics, indent=2), flush=True)


def evaluate_rl(config, checkpoint, output):
    import imageio.v2 as imageio
    import torch
    from stable_baselines3 import PPO, SAC
    from .rl_training import make_learning_env
    torch.set_num_threads(4)
    algorithm = PPO if config["algorithm"] == "ppo" else SAC
    model = algorithm.load(checkpoint, device=config["device"])
    environment = environment_of(config)
    env = make_learning_env(environment, config["step_limit"])
    start = time.monotonic()
    runs = []
    try:
        for seed in range(config["seed"], config["seed"] + config["episodes"]):
            observation, _ = env.reset(seed=seed)
            rewards = []
            success = False
            with imageio.get_writer(output / f"seed-{seed}.mp4", fps=10 if environment == "pusht" else 50) as writer:
                writer.append_data(env.render())
                for _ in range(config["step_limit"]):
                    action, _ = model.predict(observation, deterministic=True)
                    observation, reward, terminated, truncated, info = env.step(action)
                    rewards.append(float(reward))
                    writer.append_data(env.render())
                    if terminated or truncated:
                        success = bool(info.get("is_success", terminated))
                        break
            runs.append({"seed": seed, "success": success, "steps": len(rewards),
                         "best_reward": max(rewards), "sum_reward": sum(rewards), "final_reward": rewards[-1]})
    finally:
        env.close()
    return {"episodes": len(runs), "success_rate": sum(r["success"] for r in runs) / len(runs),
            "mean_best_reward": sum(r["best_reward"] for r in runs) / len(runs),
            "mean_sum_reward": sum(r["sum_reward"] for r in runs) / len(runs),
            "wall_seconds": time.monotonic() - start, "runs": runs,
            "video_camera": "native" if environment == "pusht" else "angle",
            "video_fps": 10 if environment == "pusht" else 50}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate(json.loads(args.config.read_text()), args.checkpoint, args.output)


if __name__ == "__main__":
    main()
