"""Skills + isolated Hermes roles + bounded paired retraining/evaluation."""
import csv
import io
import json
import math
import re
import time
import uuid

from .agent_jobs import AgentJobs
from .hermes import RejectedOutput
from .learning_protocol import constraints, proposal, request_body, SKILLS, validate_learning_output
from .learning_harness import checkpoint_receipt, runtime_versions, evidence_ledger, final_decision, verify_episode_traces
from .training import validate
from .training_methods import IMITATION
from .learning_environments import environment_of, evaluation_supported, ENVIRONMENTS, is_libero


def numerical_curve(folder, algorithm):
    """Only numeric measurements enter prompts; never forward raw trainer logs."""
    points = []
    if algorithm in IMITATION:
        path = folder / "run.log"
        if not path.is_file():
            return points
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 131072))
            lines = stream.read().decode(errors="replace").splitlines()
        for line in lines:
            values = {}
            for key in ("step", "loss", "l1_loss", "kld_loss", "grdn", "lr", "updt_s"):
                match = re.search(r"(?<!\w)" + key + r":([-+0-9.eE]+)", line)
                if match:
                    value = float(match[1])
                    if math.isfinite(value):
                        values[key] = value
            if "step" in values and "loss" in values:
                points.append(values)
    else:
        path = folder / "model" / "logs" / "progress.csv"
        if path.is_file():
            with path.open("rb") as stream:
                header = stream.readline().decode(errors="replace")
                offset = stream.tell()
                stream.seek(max(offset, path.stat().st_size - 131072))
                if stream.tell() > offset:
                    stream.readline()
                rows = csv.DictReader(io.StringIO(header + stream.read().decode(errors="replace")))
            for row in rows:
                point = {}
                for key in ("time/total_timesteps", "rollout/ep_rew_mean", "rollout/ep_len_mean",
                            "train/loss", "train/policy_gradient_loss", "train/value_loss",
                            "train/actor_loss", "train/critic_loss", "train/learning_rate"):
                    try:
                        value = float(row.get(key, ""))
                    except (ValueError, TypeError):
                        continue
                    if math.isfinite(value):
                        point[key] = value
                if point:
                    points.append(point)
    return points[-20:]


def interval(successes, total):
    z = 1.96
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0, center - radius), min(1, center + radius)]


def measured_comparison(baseline, candidate):
    if environment_of(baseline) != environment_of(candidate):
        raise ValueError("Learning evaluations have unmatched simulators")
    keys = ("algorithm", "input", "seeds", "episodes", "step_limit")
    if any(baseline[k] != candidate[k] for k in keys):
        raise ValueError("Learning evaluations have unmatched conditions")
    seeds = baseline["seeds"]
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Paired evaluation requires distinct episode seeds")
    arms = {}
    for name, metrics in (("baseline", baseline), ("candidate", candidate)):
        runs = metrics["runs"]
        if [r["seed"] for r in runs] != seeds or len(runs) != metrics["episodes"]:
            raise ValueError("Paired evaluation is missing or reorders episode seeds")
        if not all(type(r["success"]) is bool for r in runs):
            raise ValueError("Invalid measured success flag")
        successes = sum(r["success"] for r in runs)
        if not math.isclose(metrics["success_rate"], successes / len(runs)):
            raise ValueError("Success rate differs from episode outcomes")
        rewards = [r["best_reward"] for r in runs]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in rewards):
            raise ValueError("Evaluation rewards must be finite numeric measurements")
        if not math.isclose(metrics["mean_best_reward"], sum(rewards) / len(rewards), rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError("Mean reward differs from episode outcomes")
        if not math.isfinite(metrics["wall_seconds"]) or metrics["wall_seconds"] < 0:
            raise ValueError("Invalid evaluation duration")
        arms[name] = {"successes": successes, "episodes": len(runs),
                      "success_rate": metrics["success_rate"], "success_interval_95": interval(successes, len(runs)),
                      "mean_best_reward": metrics["mean_best_reward"], "evaluation_seconds": metrics["wall_seconds"]}
    if is_libero(baseline):
        from .libero_runtime import initial_state_index
        expected = [initial_state_index(seed, 50) for seed in seeds]
        if any([run.get('init_state_index') for run in metrics['runs']] != expected or metrics.get('initialization_count') != 50 for metrics in (baseline, candidate)):
            raise ValueError('LIBERO evaluation initial states do not match paired seeds')
    difference = arms["candidate"]["successes"] - arms["baseline"]["successes"]
    pairs = [{"seed": seed, "baseline_success": a["success"], "candidate_success": b["success"],
              "baseline_best_reward": a["best_reward"], "candidate_best_reward": b["best_reward"]}
             for seed, a, b in zip(seeds, baseline["runs"], candidate["runs"])]
    if is_libero(baseline):
        for pair, run in zip(pairs, baseline['runs']):
            pair['init_state_index'] = run['init_state_index']
    return {"algorithm": baseline["algorithm"], "environment": environment_of(baseline),
            "simulator": ENVIRONMENTS[environment_of(baseline)], "input": baseline["input"], "seeds": seeds,
            "step_limit": baseline["step_limit"], **arms, "pairs": pairs,
            "success_gains": sum(not p["baseline_success"] and p["candidate_success"] for p in pairs),
            "success_losses": sum(p["baseline_success"] and not p["candidate_success"] for p in pairs),
            "measured_verdict": "improved" if difference > 0 else "regressed" if difference < 0 else "inconclusive"}


class LearningAgentJobs(AgentJobs):
    def __init__(self, training, outputs=None, client=None):
        super().__init__(outputs=outputs, client=client, subfolder="learning-agents")
        self.training = training

    def reserve(self, episodes):
        used = set()
        for path in self.training.root.glob("*/job.json"):
            record = json.loads(path.read_text())
            cfg = record.get("config", {})
            if type(cfg.get("seed")) is int:
                used.add(cfg["seed"])
                if record.get("kind") == "evaluation":
                    used.update(range(cfg["seed"], cfg["seed"] + cfg["episodes"]))
        for path in self.folder.glob("*/job.json"):
            record = json.loads(path.read_text())
            used.update(record.get("evaluation_seeds", []))
            used.update(record.get("holdout_seeds", []))
            if type(record.get("training_seed")) is int:
                used.add(record["training_seed"])
        for path in [*self.outputs.glob("agents/*/job.json"), *self.outputs.glob("improvement-*/*.json")]:
            record = json.loads(path.read_text())
            used.update(record.get("evaluation_seeds", record.get("seeds", [])))
        for path in [self.outputs / "agent" / "report.json", self.outputs / "agent-quick" / "report.json",
                     *self.outputs.glob("runs/*/report.json")]:
            if path.is_file():
                record = json.loads(path.read_text())
                used.update(seed for values in record.get("seed_split", {}).values() for seed in values)
        first = 40000
        while any(seed in used for seed in range(first, first + episodes)):
            first += episodes
        training_seed = 500000
        while training_seed in used or training_seed in range(first, first + episodes):
            training_seed += 1
        return list(range(first, first + episodes)), training_seed

    def start(self, body):
        if set(body) - {"source_job", "steps", "eval_episodes", "step_limit", "device", "holdout_episodes"}:
            raise ValueError("Unknown learning-agent option")
        _, parent = self.training.source(body.get("source_job"))
        if parent["status"] != "completed":
            raise ValueError("Learning agents require a completed training record")
        algorithm = parent["policy"]
        imitation = algorithm in IMITATION
        if imitation and not evaluation_supported(parent["config"]):
            raise ValueError("Learning agents require the official dataset matching the simulator")
        steps, episodes, step_limit = body.get("steps", 128), body.get("eval_episodes", 3), body.get("step_limit", 100)
        holdout_episodes = body.get("holdout_episodes", 10)
        minimum = 1 if imitation else 128 if algorithm == "ppo" else 64
        maximum = 512 if imitation else 2048
        for value, low, high, label in [(steps, minimum, maximum, "steps"), (episodes, 1, 5, "eval_episodes"),
                                        (step_limit, 10, 400, "step_limit"), (holdout_episodes, 1, 20, "holdout_episodes")]:
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{label} must be an integer from {low} to {high}")
        if algorithm == "ppo" and steps % 128:
            raise ValueError("PPO agent training budget must be a multiple of 128")
        baseline = request_body(parent["config"])
        baseline.update(mode="new", algorithm=algorithm, preset="compact", steps=steps,
                        device=body.get("device", "cpu"), batch_size=min(baseline["batch_size"], 16 if imitation else 32))
        if imitation:
            baseline["episodes"] = min(baseline["episodes"], 10)
        elif algorithm == "ppo":
            baseline["rollout_steps"] = 128
        # Use the backend validator before calling any agent or writing a reservation.
        baseline = validate(baseline)
        if not self.client.health().get("connected"):
            raise RuntimeError("rx-dev Hermes gateway is not connected")
        with self.lock:
            if self.current and self.current["status"] == "running" or self.training.busy():
                raise RuntimeError("A learning experiment is already running")
            eval_seeds, training_seed = self.reserve(episodes + holdout_episodes)
            holdout_seeds = eval_seeds[episodes:]
            eval_seeds = eval_seeds[:episodes]
            baseline["seed"] = training_seed
            history = []
            blocked = []
            for path in sorted(self.folder.glob("*/evidence.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                record = json.loads(path.read_text())
                design = path.parent / "proposal.json"
                if not design.exists() or record["parent_job"]["id"] != parent["id"]:
                    continue
                result = json.loads(design.read_text())
                evaluation = path.parent / "comparison.json"
                history.append({"change": result["change"], "comparison": json.loads(evaluation.read_text()) if evaluation.exists() else None})
                same = {k:v for k,v in record["baseline_config"].items() if k != "seed"} == {k:v for k,v in baseline.items() if k != "seed"}
                if same:
                    blocked.append(result["change"])
            parent_evaluations = [job["evaluation"] for job in self.training.history()
                                  if job.get("evaluation") and job["config"].get("source_job") == parent["id"]][:5]
            evidence = {"workflow": "model_learning", "parent_job": {"id": parent["id"], "algorithm": algorithm,
                        "config": parent["config"]}, "learning_curve": numerical_curve(self.training.root / parent["id"], algorithm),
                        "parent_evaluations": parent_evaluations, "baseline_config": baseline,
                        "allowed_changes": constraints(baseline, steps), "blocked_changes": blocked,
                        "experiment_history": history, "evaluation_seeds": eval_seeds,
                        "pilot_note": "Both policies are newly initialized compact pilots, not the parent checkpoint"}
            evidence["simulator"] = ENVIRONMENTS[baseline["environment"]]
            if is_libero(baseline):
                from .libero_runtime import DATASET_REVISION, initial_state_index
                selection = json.loads((self.training.root / parent['id'] / 'demonstrations.json').read_text())
                if selection['revision'] != DATASET_REVISION or selection['task'] != evidence['simulator']['task'].replace('_', ' '):
                    raise ValueError('Source LIBERO demonstrations do not match the pinned task')
                evidence['demonstrations'] = selection
                evidence['evaluation_initial_states'] = [initial_state_index(seed, 50) for seed in eval_seeds]
            identifier = uuid.uuid4().hex
            folder = self.folder / identifier
            folder.mkdir(parents=True)
            self.cancelled.clear()
            self.current = {"id": identifier, "source_job": parent["id"], "algorithm": algorithm, "environment": baseline["environment"], "profile": "rx-dev",
                            "status": "running", "stage": "learning_analyst", "started_at": time.time(), "roles": {},
                            "skills": SKILLS, "training_seed": training_seed, "evaluation_seeds": eval_seeds,
                            "baseline_config": baseline, "step_limit": step_limit, "children": {},
                            "harness_version": 1, "holdout_seeds": holdout_seeds, "events": [],
                            "runtime_versions": runtime_versions(baseline["environment"]), "checkpoint_receipts": {}, "child_receipts": {}}
            self.save()
            (folder / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
            import threading
            self.worker = threading.Thread(target=self.run, args=(folder, evidence), daemon=True)
            self.worker.start()
            return self.state()

    def update(self, **fields):
        with self.lock:
            if "stage" in fields and fields["stage"] != self.current.get("stage"):
                self.current.setdefault("events", []).append({"stage": fields["stage"], "at": time.time()})
            super().update(**fields)

    def resume(self, body):
        if set(body) != {"job_id"}:
            raise ValueError("Expected only job_id")
        with self.lock:
            if not self.current or body["job_id"] != self.current["id"]:
                raise ValueError("Select the current saved experiment")
            if self.current["status"] not in {"interrupted", "failed", "cancelled"}:
                raise ValueError("Only interrupted, failed or cancelled experiments can resume")
            if self.current.get("harness_version") != 1:
                raise ValueError("Legacy experiments have no resumable harness state")
            if self.worker and self.worker.is_alive() or self.training.busy():
                raise RuntimeError("Experiment worker or trainer is still active")
            if not self.client.health().get("connected"):
                raise RuntimeError("rx-dev Hermes gateway is not connected")
            if self.current["runtime_versions"] != runtime_versions(self.current.get("environment")):
                raise ValueError("Runtime versions changed; start a new experiment")
            folder = self.folder / self.current["id"]
            evidence = json.loads((folder / "evidence.json").read_text())
            self.cancelled.clear()
            self.current.pop("error", None)
            self.current.pop("finished_at", None)
            self.update(status="running", resumed_at=time.time())
            import threading
            self.worker = threading.Thread(target=self.run, args=(folder, evidence), daemon=True)
            self.worker.start()
            return self.state()

    def role(self, name, evidence):
        if self.cancelled.is_set():
            raise RuntimeError("Learning experiment cancelled")
        path = self.folder / self.current["id"] / f"input_{name}.json"
        encoded = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
        if path.exists() and path.read_text() != encoded:
            raise ValueError("Saved Agent input changed; start a new experiment")
        path.write_text(encoded)
        record = self.current["roles"].get(name)
        if record and record["status"] == "completed":
            return validate_learning_output(name, record["output"], evidence)
        if record:
            # Poll the saved upstream execution rather than submitting duplicate work.
            self.update(stage=name)
            def progress(status):
                with self.lock:
                    record["status"] = status
                    self.save()
            output = self.client.poll_role(record["run_id"], name, evidence, progress, self.cancelled)
            validate_learning_output(name, output, evidence)
            record.update(status="completed", output=output)
            self.save()
            return output
        return validate_learning_output(name, super().role(name, evidence), evidence)

    def child(self, name, start):
        with self.lock:
            if self.cancelled.is_set():
                raise RuntimeError("Learning experiment cancelled")
            self.update(stage=name)
            saved = self.current["children"].get(name)
            if saved:
                path = self.training.root / saved / "job.json"
                if path.exists():
                    job = json.loads(path.read_text())
                    if job["status"] == "completed":
                        state = self.training.detail(job)
                        self.check_child_receipt(name, state)
                        return state
            # An incomplete child is rerun from scratch with the frozen request.
            job = start()
            self.current["children"][name] = job["id"]
            self.save()
        deadline = time.monotonic() + 1800
        while self.training.busy():
            if self.cancelled.wait(.2):
                self.training.stop()
                raise RuntimeError("Learning experiment cancelled")
            if time.monotonic() >= deadline:
                self.training.stop()
                raise RuntimeError("Learning child exceeded its 30-minute budget")
        state = self.training.state()
        if self.cancelled.is_set():
            raise RuntimeError("Learning experiment cancelled")
        if state["id"] != job["id"] or state["status"] != "completed":
            raise RuntimeError(f"{name} failed; inspect the linked training job log")
        self.check_child_receipt(name, state)
        return state

    def check_child_receipt(self, name, state):
        receipt = {key: state.get(key) for key in ("id", "config", "evaluation", "started_at", "finished_at")}
        if state.get("evaluation"):
            receipt["native_traces"] = verify_episode_traces(state["evaluation"], self.training.root / state["id"] / "evaluation")
        previous = self.current["child_receipts"].get(name)
        if previous and previous != receipt:
            raise ValueError("Saved child evidence changed; start a new experiment")
        self.current["child_receipts"][name] = receipt
        self.save()

    def receipt(self, name, trained):
        checkpoint, _ = self.training.source(trained["id"])
        receipt = checkpoint_receipt(checkpoint)
        previous = self.current["checkpoint_receipts"].get(name)
        if previous and previous != receipt:
            raise ValueError("Frozen checkpoint changed; start a new experiment")
        self.current["checkpoint_receipts"][name] = receipt
        self.save()

    def run(self, folder, evidence):
        try:
            self.update(stage="preflight")
            validate(request_body(evidence["baseline_config"]))
            analyst = self.role("learning_analyst", evidence)
            design = self.role("learning_designer", {**evidence, "analyst": analyst})
            candidate = proposal(design, evidence)
            (folder / "proposal.json").write_text(json.dumps(design, ensure_ascii=False, indent=2))
            self.update(candidate_config=candidate)
            owner = self.current["id"]
            training, evaluations, trained_jobs = {}, {}, {}
            for name, config in (("baseline", evidence["baseline_config"]), ("candidate", candidate)):
                trained = self.child(f"train_{name}", lambda config=config: self.training.start(request_body(config), owner=owner))
                self.receipt(name, trained)
                trained_jobs[name] = trained
                training[name] = {"job_id": trained["id"], "seconds": trained["finished_at"] - trained["started_at"],
                                  "config": config, "learning_curve": numerical_curve(self.training.root / trained["id"], config["algorithm"])}
                evaluated = self.child(f"evaluate_{name}", lambda trained=trained, config=config: self.training.evaluate(
                    {"source_job": trained["id"], "device": config["device"], "episodes": len(self.current["evaluation_seeds"]),
                     "step_limit": self.current["step_limit"]}, seed_start=self.current["evaluation_seeds"][0], owner=owner))
                evaluations[name] = evaluated["evaluation"]
            comparison = {**measured_comparison(evaluations["baseline"], evaluations["candidate"]),
                          "training": training, "design": design, "training_seed": self.current["training_seed"]}
            (folder / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2))
            self.update(comparison=comparison, stage="development_verification")
            development_ledger = evidence_ledger(evaluations["baseline"], evaluations["candidate"], comparison)
            if not development_ledger["valid"]:
                self.update(development_ledger=development_ledger)
                raise ValueError("Development evidence contradicts simulator measurements")
            # Both checkpoints and the proposal are frozen before exposing holdout results.
            holdout_evaluations = {}
            for name, config in (("baseline", evidence["baseline_config"]), ("candidate", candidate)):
                self.receipt(name, trained_jobs[name])
                evaluated = self.child(f"holdout_{name}", lambda name=name, config=config: self.training.evaluate(
                    {"source_job": trained_jobs[name]["id"], "device": config["device"],
                     "episodes": len(self.current["holdout_seeds"]), "step_limit": self.current["step_limit"]},
                    seed_start=self.current["holdout_seeds"][0], owner=owner))
                holdout_evaluations[name] = evaluated["evaluation"]
            holdout = measured_comparison(holdout_evaluations["baseline"], holdout_evaluations["candidate"])
            if set(holdout["seeds"]) & set(comparison["seeds"]) or self.current["training_seed"] in holdout["seeds"]:
                raise ValueError("Final evaluation seeds overlap development or training")
            self.update(stage="counterexample_verification")
            if is_libero(evidence['baseline_config']):
                development_states = {run['init_state_index'] for run in evaluations['baseline']['runs']}
                final_states = {run['init_state_index'] for run in holdout_evaluations['baseline']['runs']}
                if development_states & final_states:
                    raise ValueError('LIBERO final initial states overlap development states')
            ledger = evidence_ledger(holdout_evaluations["baseline"], holdout_evaluations["candidate"], holdout)
            decision = final_decision(comparison, holdout, ledger)
            bundle = {"development": development_ledger, "holdout": ledger, "decision": decision}
            (folder / "verification.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
            (folder / "holdout.json").write_text(json.dumps(holdout, ensure_ascii=False, indent=2))
            self.update(holdout=holdout, verification=bundle, decision=decision)
            self.role("learning_reviewer", {**comparison, "holdout": holdout, "verification": bundle, "decision": decision})
            self.update(status="completed", stage="completed", finished_at=time.time())
        except Exception as error:
            if isinstance(error, RejectedOutput):
                (folder / f"rejected_{self.current['stage']}.json").write_text(json.dumps(error.output, ensure_ascii=False, indent=2))
            safe = str(error) if isinstance(error, (ValueError, RuntimeError, FileNotFoundError)) else "Learning-agent experiment failed"
            self.update(status="cancelled" if self.cancelled.is_set() else "failed", error=safe, finished_at=time.time())

    def stop(self):
        with self.lock:
            self.cancelled.set()
            state = self.training.state()
            if self.current and state.get("agent_job") == self.current["id"] and self.training.busy():
                self.training.stop()
            return self.state()
