"""Read-only completion audit against real live services and persisted artifacts."""
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.hermes import Hermes, env_values, parse_output


def read_api(path):
    with urlopen("http://127.0.0.1:8787" + path, timeout=15) as response:
        return json.load(response)


def main():
    client = Hermes()
    health = read_api("/api/agents/health")
    assert health["configured"] and health["connected"] and health["ready"], health
    models = client.request("/v1/models")["data"]
    assert {"rx-dev", "rx-dev/rx-dev"} <= {m["id"] for m in models}
    enabled = [t["name"] for t in client.request("/v1/toolsets")["data"] if t["enabled"]]
    assert not enabled, "Unexpected Agent tools enabled"
    job = read_api("/api/agents/current")
    assert job["status"] == "completed", job["status"]
    assert set(job["roles"]) == {"analyst", "designer", "reviewer"}
    assert len({r["run_id"] for r in job["roles"].values()}) == 3
    for name, role in job["roles"].items():
        live = client.request("/v1/runs/" + role["run_id"])
        assert live["status"] == role["status"] == "completed"
        assert parse_output(live["output"]) == role["output"], name
    evaluation = job["evaluation"]
    assert len(evaluation["seeds"]) == len(set(evaluation["seeds"])) == 10
    source = read_api("/api/reports/" + job["report_id"])["data"]
    used = {s for values in source["seed_split"].values() for s in values}
    assert used.isdisjoint(evaluation["seeds"])
    for name in ("incumbent", "candidate"):
        results = evaluation[name]["runs"]
        assert [r["seed"] for r in results] == evaluation["seeds"]
        assert len(results) == 10 and all(r["steps"] <= evaluation["steps"] for r in results)
        assert sum(r["success"] for r in results) / 10 == evaluation[name]["summary"]["success_rate"]
    assert job["roles"]["reviewer"]["output"]["verdict"] == evaluation["measured_verdict"]
    on_disk = json.loads((ROOT / "outputs" / "agents" / job["id"] / "evaluation.json").read_text())
    assert on_disk == evaluation
    text = json.dumps([health, job], ensure_ascii=False)
    assert client.key not in text
    assert all(client.key not in p.read_text() for p in (ROOT / "frontend").iterdir() if p.is_file())
    try:
        urlopen(Request(client.base + "/v1/models"), timeout=10)
        raise AssertionError("Unauthenticated gateway request accepted")
    except HTTPError as error:
        assert error.code == 401
        error.close()
    # On this installation, prove that the shared gateway's other mappings were preserved.
    gateway_env = Path("/Volumes/T9-Workspace/gitspace/AIFde/.env")
    backups = sorted(gateway_env.parent.glob(".env.before-rx-dev-*"))
    if backups and gateway_env.exists():
        old, current = env_values(backups[0]), env_values(gateway_env)
        for key in ("HERMES_UPSTREAMS", "GATEWAY_MODEL_ALIASES"):
            before, after = json.loads(old[key]), json.loads(current[key])
            assert all(after.get(k) == v for k, v in before.items() if k != "rx-dev"), key
        assert set(old["GATEWAY_CLIENT_KEYS"].split(",")) <= set(current["GATEWAY_CLIENT_KEYS"].split(","))
        assert old.get("HERMES_DEFAULT_UPSTREAM") == current.get("HERMES_DEFAULT_UPSTREAM")
    print(json.dumps({"audit": "PASS", "profile": "rx-dev", "job_id": job["id"],
        "live_engine_roles": list(job["roles"]), "paired_episodes": 20,
        "incumbent_successes": sum(r["success"] for r in evaluation["incumbent"]["runs"]),
        "candidate_successes": sum(r["success"] for r in evaluation["candidate"]["runs"]),
        "verdict": evaluation["measured_verdict"], "secrets_exposed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
