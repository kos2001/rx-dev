"""Evaluate saved learning policies on identical seeded PushT episodes."""
import argparse
import json
from pathlib import Path
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
        metrics = evaluate_imitation(config, checkpoint, output)
    metrics.update(algorithm=config["algorithm"], environment=environment, simulator=spec, input=config["input"], source_job=config["source_job"],
                   seeds=list(range(config["seed"], config["seed"] + config["episodes"])), step_limit=config["step_limit"])
    temp = output / "metrics.tmp"
    temp.write_text(json.dumps(metrics, indent=2, allow_nan=False))
    temp.replace(output / "metrics.json")
    print(json.dumps(metrics, indent=2), flush=True)


def record_policy(config, env, predict, reset, output, seed_policy=None):
    """Record every native reward/success flag, including post-success MuJoCo steps."""
    import imageio.v2 as imageio
    environment = environment_of(config)
    start = time.monotonic()
    runs = []
    def render():
        if environment != "pusht":
            return env.unwrapped._env.physics.render(height=480, width=640, camera_id="angle")
        return env.render()
    try:
        for seed in range(config["seed"], config["seed"] + config["episodes"]):
            if seed_policy:
                seed_policy(seed)
            reset()
            observation, _ = env.reset(seed=seed)
            rewards, trace = [], []
            first_success = None
            with imageio.get_writer(output / f"seed-{seed}.mp4", fps=10 if environment == "pusht" else 50) as writer:
                writer.append_data(render())
                for step in range(config["step_limit"]):
                    observation, reward, terminated, truncated, info = env.step(predict(observation))
                    rewards.append(float(reward))
                    native_success = bool(info["is_success"])
                    if native_success and first_success is None:
                        first_success = step + 1
                    trace.append({"step": step + 1, "reward": float(reward), "is_success": native_success})
                    writer.append_data(render())
                    if truncated or terminated and environment == "pusht":
                        break
            (output / f"seed-{seed}.json").write_text(json.dumps(trace, indent=2, allow_nan=False))
            runs.append({"seed": seed, "success": first_success is not None, "steps": len(rewards),
                         "first_success_step": first_success, "final_success": trace[-1]["is_success"],
                         "best_reward": max(rewards), "sum_reward": sum(rewards), "final_reward": rewards[-1]})
    finally:
        env.close()
    return {"episodes": len(runs), "success_rate": sum(r["success"] for r in runs) / len(runs),
            "mean_best_reward": sum(r["best_reward"] for r in runs) / len(runs),
            "mean_sum_reward": sum(r["sum_reward"] for r in runs) / len(runs),
            "wall_seconds": time.monotonic() - start, "runs": runs,
            "video_camera": "native" if environment == "pusht" else "angle",
            "video_fps": 10 if environment == "pusht" else 50,
            "success_semantics": "any native success; final_success measured separately",
            "continue_after_first_success": environment != "pusht"}


def evaluate_imitation(config, checkpoint, output):
    import gymnasium as gym
    import gym_pusht  # noqa: F401
    import gym_aloha  # noqa: F401
    import torch
    from lerobot.envs.utils import preprocess_observation
    from lerobot.policies.factory import get_policy_class, make_pre_post_processors
    torch.set_num_threads(4)
    policy = get_policy_class(config["algorithm"]).from_pretrained(checkpoint).to(config["device"]).eval()
    policy.config.device = config["device"]
    pre, post = make_pre_post_processors(policy.config, pretrained_path=checkpoint,
                 preprocessor_overrides={"device_processor": {"device": config["device"]}})
    images = [feature.shape for feature in policy.config.input_features.values() if feature.type.value == "VISUAL"]
    if len(images) != 1:
        raise ValueError("Simulator evaluation requires a single image observation")
    height, width = images[0][-2:]
    spec = ENVIRONMENTS[environment_of(config)]
    env = gym.make(f"gym_{spec['type']}/{spec['task']}", obs_type="pixels_agent_pos", render_mode="rgb_array",
                   observation_height=height, observation_width=width, max_episode_steps=config["step_limit"])
    def predict(observation):
        with torch.inference_mode():
            return post(policy.select_action(pre(preprocess_observation(observation))))[0].cpu().numpy()
    return record_policy(config, env, predict, policy.reset, output, seed_policy=torch.manual_seed)


def evaluate_rl(config, checkpoint, output):
    import torch
    from stable_baselines3 import PPO, SAC
    from .rl_training import make_learning_env
    torch.set_num_threads(4)
    algorithm = PPO if config["algorithm"] == "ppo" else SAC
    model = algorithm.load(checkpoint, device=config["device"])
    env = make_learning_env(environment_of(config), config["step_limit"])
    return record_policy(config, env, lambda observation: model.predict(observation, deterministic=True)[0], lambda: None, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate(json.loads(args.config.read_text()), args.checkpoint, args.output)


if __name__ == "__main__":
    main()
