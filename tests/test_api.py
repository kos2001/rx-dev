import json
import threading
import tempfile
from pathlib import Path
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from backend.server import Handler, Jobs
from backend.agent_jobs import AgentJobs


class ApiChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.jobs = Jobs()
        cls.agent_temp = tempfile.TemporaryDirectory()
        cls.outputs = Path(cls.agent_temp.name) / 'outputs'
        fixture = cls.outputs / 'agent'
        fixture.mkdir(parents=True)
        (fixture / 'report.json').write_text(json.dumps({'seed_split':{'test':[100]}}))
        (fixture / 'planner-100.json').write_text(json.dumps([{'step':0,'reward':0}]))
        # Range-response fixture; not a playable video or a simulator result.
        (fixture / 'planner.mp4').write_bytes(bytes(range(256)))
        cls.output_patch = patch('backend.server.OUTPUTS', cls.outputs)
        cls.output_patch.start()
        cls.server.agents = AgentJobs(outputs=Path(cls.agent_temp.name))
        cls.server.work_lock = threading.Lock()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.output_patch.stop()
        cls.agent_temp.cleanup()

    def test_existing_results_and_seed_trace(self):
        with urlopen(self.base + "/api/reports/agent") as response:
            result = json.load(response)
        self.assertEqual(result["kind"], "agent")
        seed = result["data"]["seed_split"]["test"][0]
        with urlopen(self.base + f"/api/reports/agent/traces/planner/{seed}") as response:
            self.assertGreater(len(json.load(response)), 0)

    def test_media_seeking(self):
        request = Request(self.base + "/media/agent/planner.mp4", headers={"Range": "bytes=0-99"})
        with urlopen(request) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(len(response.read()), 100)
            self.assertEqual(response.headers["Accept-Ranges"], "bytes")

    def test_controller_study_is_separate_read_only_evidence(self):
        with urlopen(self.base + "/api/controller-study") as response:
            study = json.load(response)
        self.assertEqual(study["expected_test_episodes"], 30)
        self.assertIn("tuning", study)
        self.assertIn("test", study)

    def test_paths_and_unavailable_examples_are_rejected(self):
        for path in ["/media/%2e%2e/run_app.sh", "/api/reports/invalid"]:
            with self.assertRaises(HTTPError) as error:
                urlopen(self.base + path)
            self.assertEqual(error.exception.code, 400)
        request = Request(self.base + "/api/jobs", data=b'{"example":"metaworld"}', headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.server.jobs.state()["status"], "idle")

    def test_foreign_origin_cannot_launch_job(self):
        for path in ("/api/jobs", "/api/agents", "/api/agents/stop"):
            request = Request(self.base + path, data=b'{"example":"pusht-agent"}',
                              headers={"Content-Type": "application/json", "Origin": "https://example.com"})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)

    def test_agent_jobs_reject_arbitrary_prompts_and_paths(self):
        for body in [{"report_id": "../../private"}, {"report_id": "agent", "prompt": "run arbitrary code"}, {"report_id": "demo"}]:
            request = Request(self.base + "/api/agents", data=json.dumps(body).encode(),
                              headers={"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
