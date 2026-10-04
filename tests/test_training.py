import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.training import TrainingJobs, validate, training_args
from backend.server import Handler, Jobs
from backend.agent_jobs import AgentJobs


class TrainingChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.jobs = TrainingJobs(outputs=Path(self.temp.name) / "training")

    def tearDown(self):
        self.jobs.shutdown()
        self.temp.cleanup()

    def wait_done(self):
        deadline = time.monotonic() + 5
        while self.jobs.busy() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertFalse(self.jobs.busy())
        return self.jobs.state()

    def test_validation_blocks_cli_injection_and_invalid_types(self):
        for body in [{"dataset":"--policy.path=x"}, {"dataset":"../../x"},
                     {"steps":True}, {"batch_size":0}, {"device":"auto"},
                     {"episodes":1001}, {"command":"echo hi"}]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                validate(body)

    def test_methods_have_distinct_input_contracts_and_step_units(self):
        for algorithm in ("act", "diffusion"):
            config = validate({"algorithm":algorithm,"steps":1})
            args = training_args(config, Path("model"))
            self.assertIn(f"--policy.type={algorithm}", args)
            self.assertIn("--dataset.repo_id=lerobot/pusht", args)
        for algorithm in ("ppo", "sac"):
            config = validate({"algorithm":algorithm,"steps":128})
            self.assertIsNone(config["dataset"])
            self.assertIsNone(config["episodes"])
        for body in [{"algorithm":"unknown"}, {"algorithm":"ppo","steps":129},
                     {"algorithm":"ppo","steps":128,"dataset":"lerobot/pusht"},
                     {"algorithm":"sac","gamma":True}, {"algorithm":"sac","learning_rate":float('nan')},
                     {"algorithm":"act","gamma":.99}, {"mode":"resume","source_job":"../secret"}]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                validate(body)

    def test_saved_source_is_owned_and_algorithm_checked(self):
        identifier = "c" * 32
        folder = self.jobs.root / identifier
        checkpoint = folder / "model" / "checkpoints" / "last" / "pretrained_model"
        checkpoint.mkdir(parents=True)
        config = validate({"steps":1,"episodes":1,"batch_size":1})
        (folder / "job.json").write_text(json.dumps({"id":identifier,"status":"completed","policy":"act","config":config}))
        with self.assertRaises(ValueError):
            self.jobs.start({"algorithm":"diffusion","mode":"finetune","source_job":identifier})
        with self.assertRaises(ValueError):
            self.jobs.start({**config,"mode":"resume","source_job":identifier,"steps":2})
        (checkpoint / "train_config.json").write_text('{}')
        state = checkpoint.parent / "training_state"
        state.mkdir()
        (state / "training_step.json").write_text('{"step":1}')
        with self.assertRaises(ValueError):
            self.jobs.start({**config,"mode":"resume","source_job":identifier,"steps":1})
        # Never follow an external checkpoint symlink, even for an otherwise valid job.
        (checkpoint / "train_config.json").unlink()
        checkpoint.rmdir()
        external = Path(self.temp.name) / "external-checkpoint"
        external.mkdir()
        checkpoint.symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.jobs.source(identifier)
        with self.assertRaises(ValueError):
            self.jobs.source("../" + identifier)

    def test_evaluation_is_separate_from_saved_training_weights(self):
        identifier = "d" * 32
        folder = self.jobs.root / identifier
        folder.mkdir()
        (folder / "job.json").write_text(json.dumps({"id":identifier,"kind":"evaluation","status":"completed","policy":"ppo","config":{}}))
        with self.assertRaises(ValueError):
            self.jobs.source(identifier)
        with self.assertRaises(ValueError):
            self.jobs.evaluate({"source_job":identifier,"command":"echo hi"})

    def test_real_subprocess_checkpoint_and_persisted_history(self):
        launch = subprocess.Popen
        def fixture(command, **kwargs):
            output = next(a.split("=", 1)[1] for a in command if a.startswith("--output_dir="))
            script = "from pathlib import Path; import sys; p=Path(sys.argv[1])/'checkpoints/000001/pretrained_model'; p.mkdir(parents=True); (p/'model.safetensors').write_bytes(b'fixture'); print('steps:1 loss:0.25')"
            return launch([sys.executable, "-c", script, output], **kwargs)
        with patch("backend.training.subprocess.Popen", side_effect=fixture):
            started = self.jobs.start({"steps":1})
        state = self.wait_done()
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len(state["checkpoints"]), 1)
        self.assertIn("loss:0.25", "\n".join(state["logs"]))
        restored = TrainingJobs(outputs=self.jobs.root)
        self.assertEqual(restored.history()[0]["id"], started["id"])
        self.assertEqual(restored.history()[0]["status"], "completed")

    def test_exit_zero_without_weights_is_not_completed(self):
        launch = subprocess.Popen
        with patch("backend.training.subprocess.Popen", side_effect=lambda command, **kwargs:
                   launch([sys.executable, "-c", "print('no weights')"], **kwargs)):
            self.jobs.start({"steps":1})
        self.assertEqual(self.wait_done()["status"], "failed")

    def test_duplicate_start_and_stop(self):
        launch = subprocess.Popen
        with patch("backend.training.subprocess.Popen", side_effect=lambda command, **kwargs:
                   launch([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)):
            self.jobs.start({"steps":1})
            with self.assertRaises(RuntimeError):
                self.jobs.start({"steps":1})
            self.jobs.stop()
        self.assertEqual(self.wait_done()["status"], "stopped")

    def test_restart_preserves_interrupted_job(self):
        folder = self.jobs.root / ("a" * 32)
        folder.mkdir()
        (folder / "job.json").write_text(json.dumps({"id":folder.name,"status":"running"}))
        restored = TrainingJobs(outputs=self.jobs.root)
        self.assertEqual(restored.history()[0]["status"], "interrupted")

    def test_api_rejects_training_during_simulation_and_foreign_origin(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.jobs = Jobs()
        server.jobs.current = {"id":"a" * 32,"status":"running"}
        server.agents = AgentJobs(outputs=Path(self.temp.name) / "agents")
        server.training = self.jobs
        server.work_lock = threading.Lock()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            for headers, expected in [({},409), ({"Origin":"https://example.com"},403)]:
                request = Request(base + "/api/training", data=b'{"steps":1}',
                                  headers={"Content-Type":"application/json", **headers})
                with self.assertRaises(HTTPError) as error:
                    urlopen(request)
                self.assertEqual(error.exception.code, expected)
            server.jobs.current = None
            with urlopen(base + "/api/training") as response:
                self.assertEqual(json.load(response), [])
            self.jobs.current = {"id":"b" * 32,"status":"running"}
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base + "/api/jobs", data=b'{}', headers={"Content-Type":"application/json"}))
            self.assertEqual(error.exception.code, 409)
            self.jobs.current = None
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
