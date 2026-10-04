"""Local API. No frontend rendering or simulation imports in the HTTP process."""
import argparse
import json
import mimetypes
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .examples import EXAMPLES
from .agent_jobs import AgentJobs
from .training import TrainingJobs
from .training_methods import METHODS
from .learning_agents import LearningAgentJobs

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
ALLOWED_ORIGINS = {"http://127.0.0.1:3030", "http://localhost:3030"}


def read_json(path):
    return json.loads(path.read_text())


def report_dir(identifier):
    if identifier in {"agent", "agent-quick", "demo"}:
        return OUTPUTS if identifier == "demo" else OUTPUTS / identifier
    if not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise ValueError("Invalid report identifier")
    return OUTPUTS / "runs" / identifier


def reports():
    items = []
    roots = [("agent", OUTPUTS / "agent"), ("agent-quick", OUTPUTS / "agent-quick"), ("demo", OUTPUTS)]
    if (OUTPUTS / "runs").exists():
        roots += [(p.name, p) for p in (OUTPUTS / "runs").iterdir() if p.is_dir()]
    for identifier, folder in roots:
        report = folder / "report.json"
        demo = folder / "results.json"
        path = report if report.exists() else demo
        if not path.exists():
            continue
        metadata = read_json(folder / "job.json") if (folder / "job.json").exists() else {}
        # Running jobs do not publish partially completed artifacts as final results.
        if metadata and metadata.get("status") != "completed":
            continue
        items.append({"id": identifier, "kind": "agent" if report.exists() else "demo",
                      "title": metadata.get("title", {"agent": "PushT · 전체 비교", "agent-quick": "PushT · 개발 실험", "demo": "ALOHA / PushT · 동작 확인"}.get(identifier, "실험")),
                      "updated_at": path.stat().st_mtime})
    return sorted(items, key=lambda item: item["updated_at"], reverse=True)


def payload(identifier):
    folder = report_dir(identifier)
    path = folder / "report.json"
    kind = "agent"
    if not path.exists():
        path, kind = folder / "results.json", "demo"
    data = read_json(path)
    relative = folder.relative_to(OUTPUTS).as_posix()
    base = "/media/" + (relative + "/" if relative != "." else "")
    media = [{"name": p.stem, "url": base + p.name,
              "poster": base + p.with_suffix(".png").name if p.with_suffix(".png").exists() else None}
             for p in sorted(folder.glob("*.mp4"))]
    return {"id": identifier, "kind": kind, "data": data, "media": media}


class Jobs:
    def __init__(self):
        self.lock = threading.Lock()
        self.current = None
        self.process = None

    def state(self):
        with self.lock:
            if self.current is None:
                return {"status": "idle", "logs": []}
            data = dict(self.current)
            log = report_dir(data["id"]) / "run.log"
            data["logs"] = log.read_text(errors="replace").splitlines()[-40:] if log.exists() else []
            return data

    def start(self, body):
        example_id = body.get("example", "pusht-agent")
        example = next((e for e in EXAMPLES if e["id"] == example_id and e["available"]), None)
        if example is None:
            raise ValueError("This example does not have a local runner")
        steps = body.get("steps", 300 if example["mode"] == "agent" else 250)
        if type(steps) is not int or not 10 <= steps <= 500:
            raise ValueError("steps must be an integer from 10 to 500")
        quick = body.get("quick", False)
        if type(quick) is not bool:
            raise ValueError("quick must be a boolean")
        with self.lock:
            if self.current and self.current["status"] == "running":
                raise RuntimeError("An experiment is already running")
            identifier = uuid.uuid4().hex
            folder = report_dir(identifier)
            folder.mkdir(parents=True)
            module = "backend.pusht_agent" if example["mode"] == "agent" else "backend.simulation"
            command = [sys.executable, "-u", "-m", module, "--output", str(folder), "--steps", str(steps)]
            if example["mode"] == "agent" and quick:
                command.append("--quick")
            if example["mode"] == "demo":
                command += ["--environment", example_id]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR="/private/tmp/lerobot-mpl")
            log = (folder / "run.log").open("w")
            try:
                self.process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
            finally:
                log.close()
            self.current = {"id": identifier, "example": example_id, "title": example["name"],
                            "status": "running", "started_at": time.time(), "steps": steps, "quick": quick}
            self.save()
            threading.Thread(target=self.monitor, args=(self.process, identifier), daemon=True).start()
            return dict(self.current)

    def save(self):
        (report_dir(self.current["id"]) / "job.json").write_text(json.dumps(self.current, indent=2))

    def monitor(self, process, identifier):
        code = process.wait()
        with self.lock:
            if self.current["id"] == identifier:
                self.current.update(status="completed" if code == 0 else "failed", exit_code=code, finished_at=time.time())
                self.save()


class Handler(BaseHTTPRequestHandler):
    def cors(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def json(self, data, status=200):
        content = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        if self.headers.get("Origin") not in ALLOWED_ORIGINS:
            return self.json({"error": "Origin not allowed"}, 403)
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        try:
            if path == "/api/health":
                return self.json({"status": "ok", "service": "lerobot-backend"})
            if path == "/api/examples":
                return self.json({"checked_at": "2026-10-04", "examples": EXAMPLES})
            if path == "/api/reports":
                return self.json(reports())
            if path == "/api/jobs/current":
                return self.json(self.server.jobs.state())
            if path == "/api/training/current":
                return self.json(self.server.training.state())
            if path == "/api/training":
                return self.json(self.server.training.history())
            if path == "/api/training/methods":
                return self.json(METHODS)
            if path == "/api/learning-agents/current":
                return self.json(self.server.learning_agents.state())
            if path == "/api/agents/health":
                return self.json(self.server.agents.client.health())
            if path == "/api/agents/current":
                return self.json(self.server.agents.state())
            if path == "/api/controller-study":
                folder = OUTPUTS / "improvement-v2-terminal"
                return self.json({"tuning":read_json(folder / "tuning.json") if (folder / "tuning.json").exists() else None,
                                  "test":read_json(folder / "test.json") if (folder / "test.json").exists() else None,
                                  "expected_test_episodes":30})
            match = re.fullmatch(r"/api/reports/([^/]+)", path)
            if match:
                return self.json(payload(match[1]))
            match = re.fullmatch(r"/api/reports/([^/]+)/traces/(baseline|planner)/(\d+)", path)
            if match:
                folder = report_dir(match[1])
                return self.json(read_json(folder / f"{match[2]}-{int(match[3])}.json"))
            if path.startswith("/media/"):
                return self.media(path[7:])
            return self.json({"error": "Not found"}, 404)
        except FileNotFoundError:
            return self.json({"error": "Result not available"}, 404)
        except (ValueError, json.JSONDecodeError):
            return self.json({"error": "Invalid request or result"}, 400)

    def media(self, name):
        path = (OUTPUTS / name).resolve()
        if not path.is_relative_to(OUTPUTS.resolve()) or path.suffix not in {".mp4", ".png"}:
            return self.json({"error": "Invalid media path"}, 400)
        if not path.is_file():
            return self.json({"error": "Media not found"}, 404)
        size, start, end = path.stat().st_size, 0, path.stat().st_size - 1
        byte_range = self.headers.get("Range")
        if byte_range:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", byte_range)
            if not match or not any(match.groups()):
                return self.json({"error": "Unsupported byte range"}, 416)
            if not match[1]:
                start = max(0, size - int(match[2]))
            else:
                start = int(match[1])
                if match[2]:
                    end = min(end, int(match[2]))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        self.send_response(206 if byte_range else 200)
        self.cors()
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(end - start + 1))
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self):
        if self.headers.get("Origin") and self.headers["Origin"] not in ALLOWED_ORIGINS:
            return self.json({"error": "Origin not allowed"}, 403)
        path = urlsplit(self.path).path
        if path not in {"/api/jobs", "/api/agents", "/api/agents/stop", "/api/training", "/api/training/stop", "/api/training/evaluate", "/api/learning-agents", "/api/learning-agents/stop"}:
            return self.json({"error": "Not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Invalid body length")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected an object")
            with self.server.work_lock:
                if path == "/api/agents/stop":
                    return self.json(self.server.agents.stop(), 202)
                learning = getattr(self.server, "learning_agents", None)
                if path == "/api/learning-agents/stop":
                    if body:
                        raise ValueError("Expected an empty object")
                    return self.json(learning.stop(), 202)
                if learning and learning.state()["status"] == "running":
                    raise RuntimeError("A learning-agent experiment is running; use its stop button to cancel")
                if path == "/api/training/stop":
                    if body:
                        raise ValueError("Expected an empty object")
                    return self.json(self.server.training.stop(), 202)
                if self.server.jobs.state()["status"] == "running" or self.server.agents.state()["status"] == "running":
                    raise RuntimeError("A simulation or agent experiment is already running")
                if getattr(self.server, "training", None) and self.server.training.busy():
                    raise RuntimeError("Model training is already running")
                if path == "/api/training":
                    return self.json(self.server.training.start(body), 202)
                if path == "/api/training/evaluate":
                    return self.json(self.server.training.evaluate(body), 202)
                if path == "/api/learning-agents":
                    return self.json(self.server.learning_agents.start(body), 202)
                if path == "/api/agents":
                    if set(body) != {"report_id"} or not isinstance(body["report_id"], str):
                        raise ValueError("Expected only report_id")
                    folder = report_dir(body["report_id"])
                    if not (folder / "report.json").is_file():
                        raise ValueError("Agents currently support completed PushT evaluations only")
                    metadata = read_json(folder / "job.json") if (folder / "job.json").exists() else {}
                    if metadata and metadata.get("status") != "completed":
                        raise ValueError("Report is not completed")
                    return self.json(self.server.agents.start(body["report_id"], folder), 202)
                return self.json(self.server.jobs.start(body), 202)
        except (ValueError, json.JSONDecodeError) as error:
            return self.json({"error": str(error)}, 400)
        except RuntimeError as error:
            return self.json({"error": str(error)}, 409)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.jobs = Jobs()
    server.agents = AgentJobs()
    server.training = TrainingJobs()
    server.learning_agents = LearningAgentJobs(server.training)
    server.work_lock = threading.Lock()
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    print(f"Backend API: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.agents.shutdown()
        server.learning_agents.shutdown()
        server.training.shutdown()
        if server.jobs.process and server.jobs.process.poll() is None:
            server.jobs.process.terminate()
            server.jobs.process.wait(timeout=10)
        server.server_close()


if __name__ == "__main__":
    main()
