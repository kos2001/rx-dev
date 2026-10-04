"""Bounded controller ablation with independent tuning and sealed test seeds."""
import argparse
from dataclasses import asdict, replace
import json
import hashlib
from pathlib import Path

from .pusht_agent import Settings, episode, summarize, score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("tuning", "test"), required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/improvement-v2"))
    args = parser.parse_args()
    if (args.output / f"{args.stage}.json").exists():
        raise ValueError("Preserve measured studies: select a new output directory instead of overwriting")
    if args.stage == "tuning" and (args.output / "test.json").exists():
        raise ValueError("Do not retune a study after its held-out test")
    args.output.mkdir(parents=True, exist_ok=True)
    code_hash = hashlib.sha256((Path(__file__).parent / "pusht_agent.py").read_bytes()).hexdigest()
    base = Settings()
    if args.stage == "tuning":
        configs = [base, replace(base, controller_version="v2"),
                   replace(base, controller_version="v2", phase_steps=3)]
        seeds = [0, 1, 2, 3, 4]
    else:
        tuned = json.loads((args.output / "tuning.json").read_text())
        best = max(tuned["trials"], key=lambda t: score(t["summary"]))
        configs = [base, Settings(**best["settings"])]
        # Never retune against this test suite; comparisons use the same planner RNG.
        seeds = list(range(300, 330))
    trials = []
    for config in configs:
        runs = []
        for seed in seeds:
            run = episode(seed, config, 300, planner_seed=12345)
            runs.append(run)
            print(args.stage, config.controller_version, config.phase_steps, seed, run["success"], round(run["final_reward"], 3), flush=True)
        trials.append({"settings": asdict(config), "runs": runs, "summary": summarize(runs)})
        data = {"stage": args.stage, "seeds": seeds, "planner_seed": 12345, "steps": 300,
                "trials": trials, "selection_rule": "success_rate, final_reward, best_reward on tuning only",
                "controller_code_sha256":code_hash}
        (args.output / f"{args.stage}.json").write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
