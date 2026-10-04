"""Deterministic full-trace diagnostics and bounded prior-experiment memory."""
from collections import Counter
import json


def longest_gap(values):
    best = current = 0
    for value in values:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def trace_diagnostics(trace):
    rewards = [float(t["reward"]) for t in trace]
    return {"steps": len(trace), "contact_steps": sum(t.get("contacts", 0) > 0 for t in trace),
            "longest_no_contact_steps": longest_gap(t.get("contacts", 0) == 0 for t in trace),
            "longest_reward_plateau_steps": longest_gap(abs(b-a) < 1e-5 for a,b in zip(rewards, rewards[1:]))}


def experiment_history(outputs, report_id):
    records = []
    for path in sorted((outputs / "agents").glob("*/job.json"), key=lambda p:p.stat().st_mtime, reverse=True):
        job = json.loads(path.read_text())
        evaluation = job.get("evaluation")
        if job.get("report_id") != report_id or not evaluation:
            continue
        records.append({"job_id":job["id"], "settings":evaluation["candidate_settings"],
                        "seeds":evaluation["seeds"], "verdict":evaluation["measured_verdict"],
                        "incumbent":evaluation["incumbent"]["summary"], "candidate":evaluation["candidate"]["summary"]})
    return records[:12]


def report_diagnostics(data, folder):
    failures = Counter(r.get("failure", "unknown") for r in data["planner"]["runs"] if not r["success"])
    traces = []
    for run in data["planner"]["runs"]:
        path = folder / f"planner-{run['seed']}.json"
        if path.exists():
            traces.append({"seed":run["seed"], "success":run["success"], **trace_diagnostics(json.loads(path.read_text()))})
    return {"failure_counts":dict(failures), "full_trace_statistics":traces,
            "success_rule":"coverage > 0.95 (strict); reward = clip(coverage / 0.95, 0, 1)"}
