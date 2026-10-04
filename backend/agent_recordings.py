"""Reproduce a completed paired evaluation as actual simulator recordings.

Preserves the original evaluation/runtime measurements. Publishes a manifest
only after every recording agrees with its evaluated outcome.
"""
import argparse
import json
import math
from pathlib import Path

from .hermes import validate_settings
from .pusht_agent import Settings, episode


def matches(recorded, measured):
    return (recorded["success"] == measured["success"] and recorded["steps"] == measured["steps"]
            and all(math.isclose(recorded[key], measured[key], abs_tol=1e-6)
                    for key in ("final_reward", "best_reward", "position_error", "angle_error")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    folder = args.folder.resolve()
    evaluation = json.loads((folder / "evaluation.json").read_text())
    recordings = folder / "recordings"
    recordings.mkdir(exist_ok=True)
    pairs = []
    for seed in evaluation["seeds"]:
        pair = {"seed": seed}
        for name in ("incumbent", "candidate"):
            measured = next(r for r in evaluation[name]["runs"] if r["seed"] == seed)
            video = recordings / f"{name}-{seed}.mp4"
            trace = recordings / f"{name}-{seed}.json"
            result = episode(seed, Settings(**validate_settings(evaluation[f"{name}_settings"])),
                             evaluation["steps"], video=video, trace_path=trace, planner_seed=evaluation.get("planner_seed"))
            if not matches(result, measured):
                raise RuntimeError(f"Recording did not reproduce evaluation: {name} seed {seed}")
            pair[name] = {"video": f"recordings/{video.name}", "poster": f"recordings/{video.stem}.png",
                          "trace": f"recordings/{trace.name}", "result": result, "reproduced": True}
            print("RECORDED", name, seed, "success", result["success"], "final", round(result["final_reward"], 3), flush=True)
        pairs.append(pair)
    # Default to contrasting outcomes, not a cherry-picked candidate success.
    contrast = [p["seed"] for p in pairs if p["incumbent"]["result"]["success"] != p["candidate"]["result"]["success"]]
    manifest = {"status": "completed", "fps": 10, "pairs": pairs,
                "recommended_seeds": contrast or evaluation["seeds"][:1],
                "note": "Re-recorded on the same seeds/settings; outcomes checked against the original evaluation. Recording runtime is not used in performance comparison. Frames show pre-action states; final reward is the post-action measurement."}
    temp = folder / "recordings.tmp"
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    temp.replace(folder / "recordings.json")


if __name__ == "__main__":
    main()
