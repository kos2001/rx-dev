"""State-based model predictive PushT controller and reproducible experiment loop.

Uses simulator state and a known physics model, not a learned or vision policy.
Tuning seeds, validation seeds, and final test seeds are disjoint.
"""
import argparse
import json
import math
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import gymnasium as gym
import gym_pusht  # registers the prediction environment
import imageio.v2 as imageio
import numpy as np

from lerobot.envs.configs import PushtEnv
from lerobot.envs.factory import make_env


@dataclass(frozen=True)
class Settings:
    candidates: int = 24
    phase_steps: int = 5
    push_distance: float = 65
    angle_weight: float = 1.0
    fine_control: bool = False
    controller_version: str = "v1"


def wrap(angle):
    return (angle + np.pi) % (2 * np.pi) - np.pi


class Planner:
    """Replan short approach/contact/push sequences using observed block pose."""

    def __init__(self, settings, seed):
        self.settings = settings
        self.rng = np.random.default_rng(seed)
        self.model = gym.make("gym_pusht/PushT-v0", obs_type="state").unwrapped
        self.queue = []
        self.predicted_cost = None

    @staticmethod
    def cost(info, weight):
        pose, goal = info["block_pose"], info["goal_pose"]
        # Account for the T's off-center geometry rather than only its origin.
        def center(p):
            return p[:2] + np.array([-math.sin(p[2]), math.cos(p[2])]) * 45
        return (np.linalg.norm(center(pose) - center(goal)) / 100
                + weight * abs(wrap(pose[2] - goal[2]))
                - 0.6 * float(info.get("coverage", 0)))

    def restore(self, observation, info):
        self.model.reset(seed=0, options={"reset_to_state": observation})
        # _set_state rotates about the center of mass. Restore the measured origin
        # after setting angle, and restore observable end-effector velocity.
        self.model.block.angle = float(observation[4])
        self.model.block.position = observation[2:4].tolist()
        self.model.agent.position = observation[:2].tolist()
        self.model.agent.velocity = info["vel_agent"].tolist()
        self.model.space.reindex_shapes_for_body(self.model.block)
        self.model.space.reindex_shapes_for_body(self.model.agent)

    def action(self, observation, info):
        if self.queue:
            return self.queue.pop(0)
        s = self.settings
        pose = observation[2:]
        center = pose[:2] + np.array([-np.sin(pose[2]), np.cos(pose[2])]) * 45
        goal = info["goal_pose"]
        goal_center = goal[:2] + np.array([-np.sin(goal[2]), np.cos(goal[2])]) * 45
        toward_goal = goal_center - center
        goal_angle = math.atan2(toward_goal[1], toward_goal[0])
        near_goal = float(info.get("coverage", 0)) > 0.65
        plans = []
        if s.controller_version == "v2":
            self.restore(observation, info)
        # Deterministic proposals cover all contact sides; random proposals explore
        # different contact offsets and directions on subsequent replans.
        for i in range(s.candidates):
            theta = (2 * np.pi * i / 12 if i < 12 else self.rng.uniform(-np.pi, np.pi))
            outward = np.array([np.cos(theta), np.sin(theta)])
            lateral = np.array([-outward[1], outward[0]])
            offset = 0 if i < 12 else self.rng.uniform(-40, 40)
            approach = center + outward * 115 + lateral * offset
            contact = center + outward * 50 + lateral * offset
            # Either push toward the object's center or translate toward the goal.
            direction = (-outward if i % 2 == 0 else
                         np.array([np.cos(goal_angle), np.sin(goal_angle)]))
            push = contact + direction * s.push_distance
            if s.controller_version == "v2":
                # Contact the real T outline, not a circle about its center.
                # The old radial contact point can lie in the T's empty notch.
                query = center + outward * 180 + lateral * offset
                nearest = min((shape.point_query(query.tolist()) for shape in self.model.block.shapes),
                              key=lambda q:q.distance)
                surface = np.array(nearest.point)
                normal = np.array(nearest.gradient)
                approach = surface + normal * 35
                contact = surface + normal * 14
                direction = -normal if i % 2 == 0 else np.array([np.cos(goal_angle), np.sin(goal_angle)])
                push = contact + direction * s.push_distance
            if s.controller_version == "v2" and near_goal:
                for distance in (2, 5, 10, 20):
                    plans.append([approach, contact, contact + direction * distance])
            else:
                plans.append([approach, contact, push])
        # Direct local moves allow fine correction and avoid forced retreat each time.
        distances = [3, 8, 20, 45] if s.controller_version == "v2" and near_goal else [6, 15, 45] if s.fine_control and near_goal else [45]
        for distance in distances:
            for theta in np.linspace(0, 2 * np.pi, 16 if s.controller_version == "v2" and near_goal else 8, endpoint=False):
                target = observation[:2] + distance * np.array([np.cos(theta), np.sin(theta)])
                plans.append([target, target, target])
        if s.fine_control and near_goal:
            plans.append([observation[:2]] * 3)
        best, best_cost = None, float("inf")
        for plan in plans:
            self.restore(observation, info)
            total_motion = 0
            previous = observation[:2]
            for target in plan:
                target = np.clip(target, 20, 492).astype(np.float32)
                total_motion += np.linalg.norm(target - previous)
                previous = target
                for _ in range(s.phase_steps):
                    _, _, done, _, predicted = self.model.step(target)
                    if done:
                        break
                if done:
                    break
            score = self.cost(predicted, s.angle_weight) + 0.0001 * total_motion
            if s.controller_version == "v2":
                # Official task success outranks an approximate geometric cost.
                # Near the goal optimize actual overlap, rather than trading it
                # away for a smaller pose error or shorter end-effector motion.
                if done:
                    score = -1000.0 + 0.00001 * total_motion
                elif near_goal:
                    score = -4.0 * float(predicted.get("coverage", 0)) + 0.05 * self.cost(predicted, s.angle_weight)
            if score < best_cost:
                best_cost, best = score, plan
        # Execute the selected sequence, then observe and plan again.
        self.queue = [np.clip(target, 20, 492).astype(np.float32)
                      for target in best for _ in range(s.phase_steps)]
        self.predicted_cost = best_cost
        return self.queue.pop(0)

    def close(self):
        self.model.close()


def episode(seed, settings=None, steps=300, video=None, trace_path=None, planner_seed=None):
    cfg = PushtEnv(obs_type="state", episode_length=steps)
    env = make_env(cfg)["pusht"][0]
    effective_planner_seed = seed + 10000 if planner_seed is None else planner_seed
    planner = Planner(settings, effective_planner_seed) if settings else None
    writer = imageio.get_writer(video, fps=10) if video else None
    trace, best_reward, success = [], 0.0, False
    started = time.perf_counter()
    try:
        observation, vector_info = env.reset(seed=seed)
        for step in range(steps):
            info = {key: value[0] for key, value in vector_info.items() if not key.startswith("_")}
            action = (planner.action(observation[0], info) if planner else
                      np.array([256 + 150 * np.cos(step / 15),
                                256 + 150 * np.sin(step / 15)], dtype=np.float32))
            # Capture the terminal observation/info before vector autoreset replaces it.
            if writer:
                # Render the current state before SAME_STEP autoreset can replace
                # a successful terminal state with the next episode's initial state.
                frame = env.call("render")[0]
                writer.append_data(frame)
                if step == 0:
                    imageio.imwrite(Path(video).with_suffix(".png"), frame)
            next_obs, reward, terminated, truncated, next_info = env.step(action[None])
            final_info = next_info.get("final_info")
            if (terminated[0] or truncated[0]) and final_info is not None:
                if isinstance(final_info, dict):
                    info_after = {k: v[0] for k, v in final_info.items() if not k.startswith("_")}
                else:
                    info_after = final_info[0]
            else:
                info_after = {k: v[0] for k, v in next_info.items() if not k.startswith("_")}
            best_reward = max(best_reward, float(reward[0]))
            success = bool(terminated[0])
            trace.append({"step": step, "state": observation[0].tolist(), "action": action.tolist(),
                          "reward": float(reward[0]), "coverage": float(info_after.get("coverage", 0)),
                          "contacts": int(info_after.get("n_contacts", 0)),
                          "predicted_cost": planner.predicted_cost if planner else None,
                          "block_pose_after": np.asarray(info_after["block_pose"]).tolist()})
            observation, vector_info = next_obs, next_info
            if terminated[0] or truncated[0]:
                break
        pose = np.asarray(info_after["block_pose"])
        goal = np.asarray(info_after["goal_pose"])
        position_error = float(np.linalg.norm(pose[:2] - goal[:2]))
        angle_error = float(abs(wrap(pose[2] - goal[2])))
        contacts = sum(t["contacts"] > 0 for t in trace)
        if success:
            failure = None
        elif contacts == 0:
            failure = "no_contact"
        elif angle_error > 0.35:
            failure = "orientation_mismatch"
        elif position_error > 25:
            failure = "position_mismatch"
        else:
            failure = "insufficient_overlap"
        if trace_path:
            Path(trace_path).write_text(json.dumps(trace, indent=2) + "\n")
        return {"seed": seed, "success": success, "steps": len(trace),
                "planner_seed": effective_planner_seed if settings else None,
                "simulated_seconds": len(trace) / 10, "wall_seconds": time.perf_counter() - started,
                "best_reward": best_reward, "final_reward": float(reward[0]),
                "position_error": position_error, "angle_error": angle_error,
                "contact_steps": contacts, "failure": failure,
                "video": str(video) if video else None}
    finally:
        if writer:
            writer.close()
        if planner:
            planner.close()
        env.close()


def summarize(runs):
    return {"episodes": len(runs), "success_rate": float(np.mean([r["success"] for r in runs])),
            "mean_best_reward": float(np.mean([r["best_reward"] for r in runs])),
            "mean_final_reward": float(np.mean([r["final_reward"] for r in runs])),
            "mean_steps": float(np.mean([r["steps"] for r in runs])),
            "mean_wall_seconds": float(np.mean([r["wall_seconds"] for r in runs]))}


def score(summary):
    return (summary["success_rate"], summary["mean_final_reward"], summary["mean_best_reward"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="One-seed development smoke run")
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--output", type=Path, help="Isolated directory for this experiment")
    args = parser.parse_args()
    if args.steps < 1:
        parser.error("--steps must be positive")
    out = args.output or Path("outputs/agent-quick" if args.quick else "outputs/agent")
    out.mkdir(parents=True, exist_ok=True)
    tuning_seeds = [0] if args.quick else [0, 1, 2]
    validation_seeds = [10] if args.quick else [10, 11, 12]
    test_seeds = [42] if args.quick else list(range(100, 110))
    configs = [Settings(phase_steps=4, push_distance=55, angle_weight=0.7),
               Settings(phase_steps=5, push_distance=65, angle_weight=1.0),
               Settings(phase_steps=6, push_distance=80, angle_weight=1.3)]
    trials = []
    for config in configs:
        runs = [episode(seed, config, args.steps) for seed in tuning_seeds]
        trial = {"settings": asdict(config), "runs": runs, "summary": summarize(runs)}
        trials.append(trial)
        print("TUNING", json.dumps(trial["summary"]), asdict(config), flush=True)
        (out / "tuning.json").write_text(json.dumps(trials, indent=2) + "\n")
    # A feedback-driven fourth trial: when alignment was reached but no episode
    # succeeded, test finer corrections instead of blindly increasing push force.
    leader = max(trials, key=lambda t: score(t["summary"]))
    failures = [r for r in leader["runs"] if not r["success"]]
    if failures:
        base = Settings(**leader["settings"])
        if any(r["best_reward"] > 0.7 for r in failures):
            refined = replace(base, fine_control=True)
            reason = "High overlap without success: add short corrections near the goal."
        elif sum(r["failure"] == "orientation_mismatch" for r in failures) >= len(failures) / 2:
            refined = replace(base, angle_weight=base.angle_weight * 1.25)
            reason = "Orientation mismatch dominates: increase angle alignment weight."
        else:
            refined = replace(base, push_distance=base.push_distance * 1.2)
            reason = "Position/contact failures dominate: test longer pushes."
        runs = [episode(seed, refined, args.steps) for seed in tuning_seeds]
        trials.append({"settings": asdict(refined), "runs": runs,
                       "summary": summarize(runs), "feedback_reason": reason})
        print("REFINEMENT", reason, json.dumps(trials[-1]["summary"]), flush=True)
        (out / "tuning.json").write_text(json.dumps(trials, indent=2) + "\n")
    # Advance the best two tuning candidates to independent validation.
    finalists = sorted(trials, key=lambda t: score(t["summary"]), reverse=True)[:2]
    validation = []
    for finalist in finalists:
        config = Settings(**finalist["settings"])
        runs = [episode(seed, config, args.steps) for seed in validation_seeds]
        validation.append({"settings": asdict(config), "runs": runs, "summary": summarize(runs)})
        print("VALIDATION", json.dumps(validation[-1]["summary"]), flush=True)
    winner = max(validation, key=lambda t: score(t["summary"]))
    selected = Settings(**winner["settings"])
    (out / "selected_settings.json").write_text(json.dumps(asdict(selected), indent=2) + "\n")
    baseline, improved = [], []
    for seed in test_seeds:
        for name, config, results in [("baseline", None, baseline), ("planner", selected, improved)]:
            # Save representative seed video and every episode's state/action trace.
            video = out / f"{name}.mp4" if seed == test_seeds[0] else None
            result = episode(seed, config, args.steps, video, out / f"{name}-{seed}.json")
            results.append(result)
            print("TEST", name, seed, "success", result["success"], "reward", round(result["best_reward"], 3), flush=True)
    report = {"mode": "quick smoke" if args.quick else "held-out evaluation",
              "method": "state-based model predictive control; known simulator; no neural policy or LLM calls",
              "seed_split": {"tuning": tuning_seeds, "validation": validation_seeds, "test": test_seeds},
              "step_limit": args.steps, "tuning": trials, "validation": validation,
              "selected_settings": asdict(selected),
              "baseline": {"summary": summarize(baseline), "runs": baseline},
              "planner": {"summary": summarize(improved), "runs": improved}}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({name: report[name]["summary"] for name in ["baseline", "planner"]}, indent=2))


if __name__ == "__main__":
    main()
