"""Auditable analyst → designer → paired simulation → independent reviewer."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from .hermes import Hermes, RejectedOutput, ROLES, validate_settings
from .diagnostics import experiment_history, report_diagnostics

ROOT = Path(__file__).resolve().parents[1]


def experiment_evidence(folder):
    data = json.loads((folder / "report.json").read_text())
    result = {key: data[key] for key in ("method", "seed_split", "step_limit", "selected_settings", "baseline", "planner")}
    # Videos/raw traces stay local. Only numerical episode summaries and sampled
    # state/action/reward tuples enter the configured Hermes model provider.
    for name in ("baseline", "planner"):
        for run in result[name]["runs"]:
            run.pop("video", None)
    result["sampled_failure_traces"] = []
    result["diagnostics"] = report_diagnostics(data, folder)
    for run in data["planner"]["runs"]:
        if run["success"]:
            continue
        path = folder / f"planner-{run['seed']}.json"
        if path.exists():
            trace = json.loads(path.read_text())
            result["sampled_failure_traces"].append({"seed": run["seed"],
                "samples": trace[::max(1, len(trace) // 6)][-7:] + trace[-1:]})
    return result


class AgentJobs:
    def __init__(self, outputs=None, client=None, subfolder="agents"):
        self.outputs = outputs or ROOT / "outputs"
        self.folder = self.outputs / subfolder
        self.client = client or Hermes()
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.process = None
        self.worker = None
        records = sorted(self.folder.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        self.current = json.loads(records[0].read_text()) if records else None
        if self.current and self.current["status"] == "running":
            # Keep live upstream IDs visible; never start duplicate agent runs.
            self.current.update(status="interrupted", error="Backend restarted; saved Hermes run IDs remain available for inspection")
            self.save()

    def save(self):
        path = self.folder / self.current["id"] / "job.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.current, ensure_ascii=False, indent=2) + "\n")
        temp.replace(path)

    def update(self, **fields):
        with self.lock:
            self.current.update(fields)
            self.current["updated_at"] = time.time()
            self.save()

    def state(self):
        with self.lock:
            state = copy.deepcopy(self.current) if self.current else {"status": "idle"}
            if self.current:
                path = self.folder / self.current["id"] / "recordings.json"
                if path.exists():
                    state["recordings"] = json.loads(path.read_text())
                    base = f"/media/agents/{self.current['id']}/"
                    for pair in state["recordings"]["pairs"]:
                        for name in ("incumbent", "candidate"):
                            pair[name]["video"] = base + pair[name]["video"]
                            pair[name]["poster"] = base + pair[name]["poster"]
            return state

    def reserve_seeds(self, evidence):
        used = {seed for values in evidence["seed_split"].values() for seed in values}
        # Include all prior reports and agent reservations, not just this report.
        for path in [self.outputs / "agent" / "report.json", self.outputs / "agent-quick" / "report.json",
                     *self.outputs.glob("runs/*/report.json")]:
            if path.exists():
                record = json.loads(path.read_text())
                used.update(seed for values in record.get("seed_split", {}).values() for seed in values)
        for path in self.folder.glob("*/evaluation_request.json"):
            used.update(json.loads(path.read_text())["seeds"])
        for path in self.folder.glob("*/job.json"):
            used.update(json.loads(path.read_text()).get("evaluation_seeds", []))
        for path in self.outputs.glob("improvement-*/*.json"):
            used.update(json.loads(path.read_text()).get("seeds", []))
        selected, seed = [], 200
        while len(selected) < 10:
            if seed not in used:
                selected.append(seed)
            seed += 1
        return selected

    def start(self, identifier, report_folder):
        evidence = experiment_evidence(report_folder)
        evidence["experiment_history"] = experiment_history(self.outputs, identifier)
        evidence["blocked_settings"] = [e["settings"] for e in evidence["experiment_history"]]
        validate_settings(evidence["selected_settings"])
        if not self.client.health().get("connected"):
            raise RuntimeError("rx-dev Hermes gateway is not connected")
        with self.lock:
            if self.current and self.current["status"] == "running":
                raise RuntimeError("An agent experiment is already running")
            job_id = uuid.uuid4().hex
            folder = self.folder / job_id
            folder.mkdir(parents=True)
            self.cancelled.clear()
            self.current = {"id": job_id, "report_id": identifier, "profile": "rx-dev",
                "status": "running", "stage": "analyst", "started_at": time.time(), "roles": {},
                "evaluation_seeds": self.reserve_seeds(evidence), "step_limit": evidence["step_limit"]}
            self.save()
            (folder / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
            self.worker = threading.Thread(target=self.run, args=(folder, evidence), daemon=True)
            self.worker.start()
            return self.state()

    def role(self, name, evidence):
        self.update(stage=name)
        accepted = self.client.start_role(name, evidence, self.current["id"])
        run_id = accepted.get("run_id")
        if not isinstance(run_id, str):
            raise RuntimeError("Hermes did not return a run_id")
        with self.lock:
            from .learning_protocol import LEARNING_ROLES
            self.current["roles"][name] = {"name": {**ROLES, **LEARNING_ROLES}[name], "run_id": run_id, "status": "started"}
            self.save()

        def progress(status):
            with self.lock:
                if self.current["roles"][name]["status"] != status:
                    self.current["roles"][name]["status"] = status
                    self.save()
        output = self.client.poll_role(run_id, name, evidence, progress, self.cancelled)
        with self.lock:
            self.current["roles"][name].update(status="completed", output=output)
            self.save()
        return output

    def run(self, folder, evidence):
        try:
            analyst = self.role("analyst", evidence)
            designer = self.role("designer", {**evidence, "analyst": analyst})
            request = {"incumbent_settings": evidence["selected_settings"],
                       "candidate_settings": validate_settings(designer["settings"]),
                       "seeds": self.current["evaluation_seeds"], "steps": evidence["step_limit"], "planner_seed":12345}
            (folder / "evaluation_request.json").write_text(json.dumps(request, indent=2))
            self.update(stage="simulation")
            if self.cancelled.is_set():
                raise RuntimeError("Agent experiment cancelled")
            with (folder / "simulation.log").open("w") as log:
                self.process = subprocess.Popen([sys.executable, "-u", "-m", "backend.agent_evaluation",
                    "--folder", str(folder)], cwd=ROOT,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR="/private/tmp/lerobot-mpl"),
                    stdout=log, stderr=subprocess.STDOUT)
                code = self.process.wait()
            if code:
                raise RuntimeError("Paired simulator evaluation failed; inspect local simulation.log")
            evaluation = json.loads((folder / "evaluation.json").read_text())
            self.update(evaluation=evaluation)
            self.role("reviewer", {**evaluation, "designer": designer})
            self.update(status="completed", stage="completed", finished_at=time.time())
        except Exception as error:
            if isinstance(error, RejectedOutput) and self.current.get("stage") in ROLES:
                # Local-only record of what the model proposed; never exposed via job.json/API.
                (folder / f"rejected_{self.current['stage']}.json").write_text(
                    json.dumps(error.output, ensure_ascii=False, indent=2))
            # Restrict errors to our own messages; raw upstream/provider data stays private.
            safe = str(error) if isinstance(error, (ValueError, RuntimeError, FileNotFoundError)) else "Agent experiment failed"
            self.update(status="cancelled" if self.cancelled.is_set() else "failed", error=safe, finished_at=time.time())

    def stop(self):
        self.cancelled.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
        return self.state()

    def shutdown(self):
        self.stop()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=20)
