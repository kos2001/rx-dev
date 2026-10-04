"""Real, bounded learning/evaluation checks. This is not a performance benchmark."""
import argparse
import json
from pathlib import Path
import time

from backend.training import TrainingJobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Choose a new output directory to preserve previous verification results")
    jobs = TrainingJobs(outputs=args.output)
    results = []

    def finish(job, label):
        print(f"{label}: {job['id']}", flush=True)
        jobs.process.wait(timeout=600)
        while jobs.busy():
            time.sleep(.02)
        state = jobs.state()
        results.append({"label": label, "id": state["id"], "status": state["status"],
                        "evaluation": state.get("evaluation"), "checkpoints": state["checkpoints"]})
        (args.output / "verification.json").write_text(json.dumps(results, indent=2))
        if state["status"] != "completed":
            raise RuntimeError(f"{label} failed:\n" + "\n".join(state["logs"][-20:]))
        print(f"{label}: completed", flush=True)
        return state

    try:
        for algorithm in ("act", "diffusion", "ppo", "sac"):
            config = {"algorithm": algorithm, "device": "cpu", "batch_size": 1 if algorithm in {"act", "diffusion"} else 8,
                      "steps": 1 if algorithm in {"act", "diffusion"} else 128 if algorithm == "ppo" else 64}
            if algorithm in {"act", "diffusion"}:
                config["episodes"] = 1
            trained = finish(jobs.start(config), f"{algorithm}/new")
            if algorithm in {"ppo", "sac"}:
                info = json.loads((args.output / trained["id"] / "model" / "training_info.json").read_text())
                if info["gradient_updates"] < 1:
                    raise RuntimeError("RL runner saved a model without gradient updates")
            resumed = finish(jobs.start({**config, "mode": "resume", "source_job": trained["id"],
                                       "steps": 2 if algorithm in {"act", "diffusion"} else config["steps"]}), f"{algorithm}/resume")
            if algorithm in {"act", "diffusion"}:
                finish(jobs.start({**config, "mode": "finetune", "source_job": trained["id"]}), f"{algorithm}/finetune")
            finish(jobs.evaluate({"source_job": resumed["id"], "device": "cpu", "episodes": 1, "step_limit": 10}), f"{algorithm}/evaluation")
        print(f"Verified {len(results)} real runs. Results: {args.output / 'verification.json'}", flush=True)
    finally:
        jobs.shutdown()


if __name__ == "__main__":
    main()
