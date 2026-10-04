"""One bounded paired simulation; no LLM calls inside the control loop."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path

from .hermes import validate_settings
from .pusht_agent import Settings, episode, summarize


def measured_verdict(incumbent, candidate):
    old_success = sum(r["success"] for r in incumbent)
    new_success = sum(r["success"] for r in candidate)
    if new_success > old_success:
        return "improved"
    if new_success < old_success:
        return "regressed"
    # Small reward changes with equal success remain inconclusive, not promoted.
    return "inconclusive"


def wilson_interval(successes, total):
    z = 1.96
    p = successes / total
    center = (p + z*z/(2*total))/(1+z*z/total)
    width = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/(1+z*z/total)
    return [max(0,center-width), min(1,center+width)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads((args.folder / "evaluation_request.json").read_text())
    old = Settings(**validate_settings(request["incumbent_settings"]))
    new = Settings(**validate_settings(request["candidate_settings"]))
    seeds, steps = request["seeds"], request["steps"]
    if (not isinstance(seeds, list) or len(seeds) != 10 or len(set(seeds)) != 10
        or not all(type(s) is int and 0 <= s <= 1000000 for s in seeds)
        or type(steps) is not int or not 10 <= steps <= 500):
        raise ValueError("Invalid evaluation budget")
    incumbent, candidate = [], []
    for seed in seeds:
        for name, config, runs in [("incumbent", old, incumbent), ("candidate", new, candidate)]:
            result = episode(seed, config, steps, planner_seed=request.get("planner_seed"))
            runs.append(result)
            print(name, seed, "success", result["success"], "final", round(result["final_reward"], 3), flush=True)
    wins = sum(n["final_reward"] > o["final_reward"] + 1e-6 for o, n in zip(incumbent, candidate))
    losses = sum(n["final_reward"] < o["final_reward"] - 1e-6 for o, n in zip(incumbent, candidate))
    data = {
        "seeds": seeds, "steps": steps, "incumbent_settings": asdict(old),
        "candidate_settings": asdict(new), "incumbent": {"summary": summarize(incumbent), "runs": incumbent},
        "candidate": {"summary": summarize(candidate), "runs": candidate},
        "paired_reward": {"wins": wins, "losses": losses, "ties": len(seeds) - wins - losses},
        "measured_verdict": measured_verdict(incumbent, candidate),
        "planner_seed":request.get("planner_seed"),
        "success_intervals_95":{"incumbent":wilson_interval(sum(r["success"] for r in incumbent),len(seeds)),
                                "candidate":wilson_interval(sum(r["success"] for r in candidate),len(seeds))},
        "scope": "One development experiment on new disjoint seeds; not statistical proof or deployment approval",
    }
    (args.folder / "evaluation.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
