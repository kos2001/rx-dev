"""PPO/SAC learning from PushT and MuJoCo ALOHA simulator interactions."""
import argparse
import json
from pathlib import Path

import gymnasium as gym
import gym_pusht  # noqa: F401 — registers the environment
import numpy as np
from .learning_environments import ENVIRONMENTS, environment_of


class NormalizedPushT(gym.Wrapper):
    """Expose normalized state and target-position actions to an MLP policy."""
    def __init__(self, step_limit=300):
        super().__init__(gym.make("gym_pusht/PushT-v0", obs_type="state", render_mode="rgb_array",
                                  max_episode_steps=step_limit, visualization_width=384, visualization_height=384))
        self.observation_space = gym.spaces.Box(-1, 1, shape=(6,), dtype=np.float32)
        self.action_space = gym.spaces.Box(-1, 1, shape=(2,), dtype=np.float32)

    @staticmethod
    def observation(state):
        return np.concatenate((np.clip(state[:4] / 256 - 1, -1, 1),
                               [np.sin(state[4]), np.cos(state[4])])).astype(np.float32)

    def reset(self, **kwargs):
        state, info = self.env.reset(**kwargs)
        return self.observation(state), info

    def step(self, action):
        state, reward, terminated, truncated, info = self.env.step((np.clip(action, -1, 1) + 1) * 256)
        return self.observation(state), reward, terminated, truncated, info


class NormalizedAloha(gym.Wrapper):
    """Privileged simulator state, bounded joint increments and gripper targets.

    gym-aloha 0.1.4 has no state observation mode. Its pinned task exposes
    object poses and joint velocities through dm_control physics.
    """
    def __init__(self, environment, step_limit=300):
        import gym_aloha  # noqa: F401
        spec = ENVIRONMENTS[environment]
        super().__init__(gym.make(f"gym_aloha/{spec['task']}", obs_type="pixels_agent_pos",
                                 render_mode="rgb_array", max_episode_steps=step_limit,
                                 visualization_width=384, visualization_height=288))
        self.physics = self.env.unwrapped._env.physics
        self.task = self.env.unwrapped._env.task
        size = 14 + self.physics.data.qpos.size - 16 + self.physics.data.qvel.size
        self.observation_space = gym.spaces.Box(-1, 1, shape=(size,), dtype=np.float32)
        self.action_space = gym.spaces.Box(-1, 1, shape=(14,), dtype=np.float32)

    def observation(self):
        joints = self.task.get_qpos(self.physics)
        objects = self.task.get_env_state(self.physics)
        return np.concatenate((np.clip(joints / np.pi, -1, 1), np.clip(objects / 2, -1, 1),
                               np.clip(self.physics.data.qvel / 10, -1, 1))).astype(np.float32)

    def render(self):
        # Recording camera only; state inputs and native top-camera observations
        # used by the environment remain the same.
        return self.physics.render(height=480, width=640, camera_id="angle")

    def reset(self, **kwargs):
        _, info = self.env.reset(**kwargs)
        return self.observation(), info

    def step(self, action):
        action = np.clip(np.asarray(action), -1, 1)
        target = np.clip(self.task.get_qpos(self.physics) + .08 * action, -np.pi, np.pi)
        target[[6, 13]] = (action[[6, 13]] + 1) / 2
        _, reward, terminated, truncated, info = self.env.step(target)
        return self.observation(), reward, terminated, truncated, info


def make_learning_env(environment="pusht", step_limit=300):
    return NormalizedPushT(step_limit) if environment == "pusht" else NormalizedAloha(environment, step_limit)


def train(config, output, checkpoint=None):
    import torch
    from stable_baselines3 import PPO, SAC
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.monitor import Monitor
    from .training_runner import check_device

    check_device(config["device"])
    torch.set_num_threads(4)
    output.mkdir(parents=True)
    environment = environment_of(config)
    spec = ENVIRONMENTS[environment]
    env = Monitor(make_learning_env(environment))
    algorithm = PPO if config["algorithm"] == "ppo" else SAC

    class SavePolicy(BaseCallback):
        def _on_step(self):
            if self.n_calls % 1000 == 0:
                self.model.save(output / "policy")
            return True

    try:
        if checkpoint:
            model = algorithm.load(checkpoint, env=env, device=config["device"])
            replay = checkpoint.parent / "replay_buffer.pkl"
            if config["algorithm"] == "sac":
                if not replay.is_file():
                    raise ValueError("SAC continuation requires the saved replay buffer")
                model.load_replay_buffer(replay)
        else:
            kwargs = {"learning_rate": config["learning_rate"], "gamma": config["gamma"],
                      "batch_size": config["batch_size"], "seed": config["seed"],
                      "device": config["device"], "verbose": 1}
            if config["algorithm"] == "ppo":
                kwargs.update(n_steps=config["rollout_steps"], n_epochs=10)
            else:
                kwargs.update(buffer_size=100000, learning_starts=32, train_freq=1, gradient_steps=1)
            model = algorithm("MlpPolicy", env, **kwargs)
        model.set_logger(configure(str(output / "logs"), ["stdout", "csv"]))
        print(f"{config['algorithm'].upper()}: {spec['name']} privileged state input, native reward, {config['steps']} additional environment steps", flush=True)
        model.learn(total_timesteps=config["steps"], reset_num_timesteps=not bool(checkpoint), callback=SavePolicy())
        model.logger.dump(model.num_timesteps)
        model.save(output / "policy")
        if config["algorithm"] == "sac":
            model.save_replay_buffer(output / "replay_buffer.pkl")
        (output / "training_info.json").write_text(json.dumps({"algorithm": config["algorithm"],
            "environment": environment, "simulator": spec, "observation": spec["state_input"],
            "action": "normalized target position" if environment == "pusht" else "joint increments up to 0.08 radians + gripper targets",
            "reward": "native simulator reward", "num_timesteps": model.num_timesteps,
            "gradient_updates": model._n_updates, "seed": config["seed"], "config": config}, indent=2))
        print(f"Saved trained policy: {model.num_timesteps} total steps, {model._n_updates} gradient updates", flush=True)
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    train(json.loads(args.config.read_text()), args.output_dir, args.checkpoint)


if __name__ == "__main__":
    main()
