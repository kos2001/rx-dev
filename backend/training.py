"""Persisted local LeRobot training jobs; no ML imports in the HTTP server."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
import math

from .training_methods import IMITATION, REINFORCEMENT
from .learning_environments import ENVIRONMENTS, environment_of, evaluation_supported

ROOT = Path(__file__).resolve().parents[1]


def validate(body):
    if set(body) - {"dataset", "device", "steps", "batch_size", "episodes", "seed", "algorithm",
                    "preset", "mode", "source_job", "learning_rate", "gamma", "rollout_steps", "environment"}:
        raise ValueError("Unknown training option")
    config = {"dataset": "lerobot/pusht", "device": "cpu", "steps": 1000,
              "batch_size": 8, "episodes": 10, "seed": 1000, "algorithm": "act",
              "preset": "compact", "mode": "new", **body}
    config["environment"] = body.get("environment", environment_of(body))
    if not isinstance(config["environment"], str) or config["environment"] not in ENVIRONMENTS:
        raise ValueError("environment must be pusht, aloha or transfer")
    if "dataset" not in body:
        config["dataset"] = ENVIRONMENTS[config["environment"]]["dataset"]
    for key, value in ENVIRONMENTS.items():
        if config["dataset"] == value["dataset"] and config["environment"] != key:
            raise ValueError("Dataset and simulator environment must match")
    algorithm = config["algorithm"]
    if not isinstance(algorithm, str) or algorithm not in IMITATION | REINFORCEMENT:
        raise ValueError("algorithm must be act, diffusion, ppo or sac")
    if config["mode"] not in ("new", "finetune", "resume"):
        raise ValueError("mode must be new, finetune or resume")
    if config["preset"] not in ("compact", "standard"):
        raise ValueError("preset must be compact or standard")
    source = config.get("source_job")
    if config["mode"] != "new":
        if not isinstance(source, str) or not re.fullmatch(r"[a-f0-9]{32}", source):
            raise ValueError("Select a saved training job")
    elif source is not None:
        raise ValueError("New training does not take source_job")
    if not isinstance(config["dataset"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", config["dataset"]
    ):
        raise ValueError("dataset must be a Hugging Face namespace/name")
    if config["device"] not in ("cpu", "mps", "cuda"):
        raise ValueError("device must be cpu, mps or cuda")
    for key, low, high in [("steps", 1, 1000000 if algorithm in REINFORCEMENT else 100000), ("batch_size", 1, 128),
                           ("episodes", 1, 1000), ("seed", 0, 2147483647)]:
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise ValueError(f"{key} must be an integer from {low} to {high}")
    if algorithm in IMITATION:
        if any(key in body for key in ("gamma", "rollout_steps", "learning_rate")):
            raise ValueError("RL options only apply to PPO and SAC")
    else:
        if "dataset" in body or "episodes" in body:
            raise ValueError("PPO/SAC collect simulator experience; no demonstration dataset is used")
        if config["mode"] == "finetune":
            raise ValueError("Use resume to continue a PPO/SAC checkpoint")
        config.update(dataset=None, episodes=None)
        config.setdefault("learning_rate", 0.0003)
        config.setdefault("gamma", 0.99)
        config.setdefault("rollout_steps", 128)
        for key, low, high in [("learning_rate", 1e-6, 0.01), ("gamma", 0.8, 0.9999)]:
            if type(config[key]) not in (int, float) or not math.isfinite(config[key]) or not low <= config[key] <= high:
                raise ValueError(f"{key} must be a finite number from {low} to {high}")
        rollout = config["rollout_steps"]
        if type(rollout) is not int or not 32 <= rollout <= 2048:
            raise ValueError("rollout_steps must be an integer from 32 to 2048")
        if config["batch_size"] < 2 or config["steps"] < 32:
            raise ValueError("RL requires at least 32 environment steps and batch_size >= 2")
        if algorithm == "ppo" and (config["steps"] % rollout or rollout % config["batch_size"]):
            raise ValueError("PPO steps must be a multiple of rollout_steps; rollout_steps must be a multiple of batch_size")
    return config


def training_args(config, output, source=None):
    algorithm = config["algorithm"]
    args = [f"--policy.type={algorithm}", f"--dataset.repo_id={config['dataset']}",
            f"--dataset.episodes={json.dumps(list(range(config['episodes'])))}",
            "--dataset.video_backend=pyav", f"--policy.device={config['device']}",
            "--policy.push_to_hub=false", "--wandb.enable=false", "--num_workers=0",
            f"--steps={config['steps']}", f"--batch_size={config['batch_size']}",
            f"--seed={config['seed']}", "--env_eval_freq=0", "--log_freq=1",
            f"--save_freq={min(1000, config['steps'])}", f"--output_dir={output}"]
    if config["mode"] == "resume":
        # Load architecture, dataset and optimizer configuration from the saved run.
        return [f"--config_path={source / 'train_config.json'}", "--resume=true",
                f"--steps={config['steps']}", f"--output_dir={output}",
                f"--policy.device={config['device']}", "--policy.push_to_hub=false",
                "--wandb.enable=false", "--log_freq=1", "--num_workers=0", "--env_eval_freq=0"]
    if source:
        # Keep the pretrained architecture and processors; reset optimizer for fine-tuning.
        args = [arg for arg in args if not arg.startswith("--policy.type=")]
        args.append(f"--policy.path={source}")
    elif config["preset"] == "compact":
        if algorithm == "act":
            args += ["--policy.dim_model=128", "--policy.dim_feedforward=512", "--policy.n_encoder_layers=2",
                     "--policy.n_vae_encoder_layers=2", "--policy.chunk_size=16", "--policy.n_action_steps=16"]
        else:
            args += ["--policy.down_dims=[128,256,512]", "--policy.horizon=16", "--policy.n_action_steps=8"]
    return args


class TrainingJobs:
    def __init__(self, outputs=None, python=None):
        self.root = Path(outputs).resolve() if outputs is not None else ROOT / "outputs" / "training"
        self.python = python or sys.executable
        self.lock = threading.RLock()
        self.current = None
        self.process = None
        self.root.mkdir(parents=True, exist_ok=True)
        # No process ownership survives a server restart. Preserve the artifacts.
        for path in self.root.glob("*/job.json"):
            job = json.loads(path.read_text())
            if job["status"] in {"running", "stopping"}:
                job.update(status="interrupted", finished_at=time.time())
                path.write_text(json.dumps(job, indent=2))

    def save(self):
        path = self.root / self.current["id"] / "job.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.current, indent=2))
        temp.replace(path)

    def detail(self, job):
        result = dict(job)
        folder = self.root / job["id"]
        log = folder / "run.log"
        result["logs"] = []
        if log.exists():
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 32768))
                result["logs"] = stream.read().decode(errors="replace").splitlines()[-60:]
        result["checkpoints"] = [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
                                 for p in sorted((folder / "model" / "checkpoints").glob("*/pretrained_model"))
                                 if (p / "model.safetensors").is_file()]
        rl = folder / "model" / "policy.zip"
        if rl.is_file():
            result["checkpoints"] = [str(rl.relative_to(ROOT)) if rl.is_relative_to(ROOT) else str(rl)]
        metrics = folder / "evaluation" / "metrics.json"
        result["evaluation"] = json.loads(metrics.read_text()) if metrics.is_file() and job["status"] == "completed" else None
        result["videos"] = []
        if result["evaluation"] and folder.is_relative_to(ROOT / "outputs"):
            result["videos"] = ["/media/" + p.relative_to(ROOT / "outputs").as_posix()
                                for p in sorted((folder / "evaluation").rglob("*.mp4"))]
        return result

    def history(self):
        with self.lock:
            return [self.detail(json.loads(p.read_text())) for p in
                    sorted(self.root.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)]

    def state(self):
        with self.lock:
            return self.detail(self.current) if self.current else {"status": "idle", "logs": []}

    def busy(self):
        return self.state()["status"] in {"running", "stopping"}

    def start(self, body, owner=None):
        config = validate(body)
        source = None
        if config["mode"] != "new":
            source, original = self.source(config["source_job"])
            if original["policy"] != config["algorithm"]:
                raise ValueError("Checkpoint algorithm must match the selected method")
            if environment_of(original["config"]) != config["environment"]:
                raise ValueError("Checkpoint simulator must match the selected environment")
            if config["algorithm"] in REINFORCEMENT:
                for key in ("batch_size", "seed", "learning_rate", "gamma", "rollout_steps"):
                    if config[key] != original["config"][key]:
                        raise ValueError(f"RL continuation retains the original {key}")
                if config["algorithm"] == "sac" and not (source.parent / "replay_buffer.pkl").is_file():
                    raise ValueError("SAC continuation requires the saved replay buffer")
            if config["mode"] == "resume" and config["algorithm"] in IMITATION:
                saved = original["config"]
                for key in ("dataset", "episodes", "batch_size", "seed"):
                    if config[key] != saved[key]:
                        raise ValueError(f"Resume must retain the original {key}; use fine-tuning to change the dataset")
                state = source.parent / "training_state" / "training_step.json"
                if not state.is_file():
                    raise ValueError("Checkpoint has no optimizer/training state to resume")
                if config["steps"] <= json.loads(state.read_text())["step"]:
                    raise ValueError("Resume steps must exceed the saved training step (total target, not additional steps)")
            config["preset"] = original["config"].get("preset", "standard")
        return self.launch(config, source, owner=owner)

    def source(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValueError("Invalid source job")
        folder = self.root / identifier
        metadata = folder / "job.json"
        if not metadata.is_file():
            raise ValueError("Saved training job not found")
        job = json.loads(metadata.read_text())
        if job.get("kind", "training") != "training" or job["status"] in {"running", "stopping"}:
            raise ValueError("Select a finished or stopped training job with a checkpoint")
        if job["policy"] in REINFORCEMENT:
            checkpoint = folder / "model" / "policy.zip"
        else:
            checkpoint = folder / "model" / "checkpoints" / "last" / "pretrained_model"
        if not checkpoint.resolve().is_relative_to(folder.resolve()) or not checkpoint.exists():
            raise ValueError("Saved checkpoint is unavailable")
        return checkpoint, job

    def evaluate(self, body, seed_start=20000, owner=None):
        if set(body) - {"source_job", "device", "episodes", "step_limit"}:
            raise ValueError("Unknown evaluation option")
        source, original = self.source(body.get("source_job"))
        if original["policy"] in IMITATION and not evaluation_supported(original["config"]):
            raise ValueError("Select the official dataset matching the simulator for policy evaluation")
        config = {"source_job": original["id"], "algorithm": original["policy"],
                  "environment": environment_of(original["config"]),
                  "device": "cpu", "episodes": 5, "step_limit": 300, "seed": seed_start, **body}
        if type(seed_start) is not int or not 0 <= seed_start <= 2147483600:
            raise ValueError("Invalid evaluation seed")
        if config["device"] not in ("cpu", "mps", "cuda"):
            raise ValueError("Invalid evaluation device")
        for key, low, high in [("episodes", 1, 20), ("step_limit", 10, 400)]:
            if type(config[key]) is not int or not low <= config[key] <= high:
                raise ValueError(f"{key} must be an integer from {low} to {high}")
        config["input"] = ENVIRONMENTS[config["environment"]]["state_input"] if original["policy"] in REINFORCEMENT else "pixels_agent_pos"
        return self.launch(config, source, kind="evaluation", owner=owner)

    def launch(self, config, source=None, kind="training", owner=None):
        with self.lock:
            if self.busy():
                raise RuntimeError("Training is already running")
            identifier = uuid.uuid4().hex
            folder = self.root / identifier
            folder.mkdir()
            (folder / "request.json").write_text(json.dumps(config, indent=2))
            if kind == "evaluation":
                command = [self.python, "-u", "-m", "backend.policy_evaluation",
                           "--config", str(folder / "request.json"), "--checkpoint", str(source),
                           "--output", str(folder / "evaluation")]
            elif config["algorithm"] in REINFORCEMENT:
                command = [self.python, "-u", "-m", "backend.rl_training", "--config", str(folder / "request.json"),
                           f"--output_dir={folder / 'model'}"]
                if source:
                    command += ["--checkpoint", str(source)]
            else:
                command = [self.python, "-u", "-m", "backend.training_runner", *training_args(config, folder / "model", source)]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                               HF_HOME=str(ROOT / "outputs" / "hf-cache"),
                               TORCH_HOME=str(ROOT / "outputs" / "torch-cache"),
                               HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")
            with (folder / "run.log").open("w") as log:
                self.process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log,
                                                stderr=subprocess.STDOUT, start_new_session=True)
            self.current = {"id": identifier, "status": "running", "policy": config["algorithm"], "kind": kind,
                            "config": config, "started_at": time.time(), "command": command}
            if owner:
                self.current["agent_job"] = owner
            self.save()
            threading.Thread(target=self.monitor, args=(self.process, identifier), daemon=True).start()
            return self.state()

    def monitor(self, process, identifier):
        code = process.wait()
        with self.lock:
            if self.current["id"] != identifier:
                return
            stopped = self.current["status"] == "stopping"
            checkpoints = self.detail(self.current)["checkpoints"]
            artifact = (self.root / identifier / "evaluation" / "metrics.json").is_file() if self.current["kind"] == "evaluation" else bool(checkpoints)
            status = "stopped" if stopped else "completed" if code == 0 and artifact else "failed"
            self.current.update(status=status, exit_code=code, finished_at=time.time())
            if code == 0 and not artifact and not stopped:
                self.current["error"] = "Runner exited without the expected saved artifact"
            self.save()

    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.current["status"] = "stopping"
                self.save()
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                threading.Thread(target=self.finish_stop, args=(self.process,), daemon=True).start()
            return self.state()

    @staticmethod
    def finish_stop(process):
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

    def shutdown(self):
        self.stop()
        if self.process:
            self.finish_stop(self.process)
