import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from backend.agent_jobs import AgentJobs, experiment_evidence
from backend.hermes import Hermes, RejectedOutput, parse_output, validate_output, validate_settings

SETTINGS = {"candidates": 24, "phase_steps": 5, "push_distance": 65,
            "angle_weight": 1.0, "fine_control": False}


class HermesChecks(unittest.TestCase):
    def test_settings_reject_extra_keys_types_and_budget(self):
        self.assertEqual(validate_settings(SETTINGS), SETTINGS)
        for updates in [{"command": "touch arbitrary"}, {"candidates": True},
                        {"candidates": 10000}, {"phase_steps": 1.5},
                        {"fine_control": "yes"}, {"angle_weight": float("nan")},
                        {"push_distance": float("inf")}, {"controller_version": []},
                        {"controller_version": "v3"}]:
            with self.assertRaises(ValueError):
                validate_settings({**SETTINGS, **updates})

    def test_outputs_validate_evidence_and_verdict(self):
        with self.assertRaises(ValueError):
            validate_output("analyst", {"summary": "test", "findings": [{"failure": "x", "seeds": [999],
                "evidence": "x", "recommendation": "x"}]}, {"seed_split": {"test": [100]}})
        with self.assertRaises(ValueError):
            validate_output("reviewer", {"verdict": "improved", "summary": "x", "evidence": [],
                "limitations": [], "next_step": "x"}, {"measured_verdict": "regressed"})
        self.assertEqual(parse_output('```json\n{"ok":true}\n```'), {"ok": True})
        with self.assertRaises(ValueError):
            parse_output("not JSON")

    def test_designer_changes_one_setting_and_does_not_repeat_history(self):
        evidence = {"selected_settings":SETTINGS,"blocked_settings":[{**SETTINGS,"fine_control":True}]}
        for proposal in [{**SETTINGS,"fine_control":True}, {**SETTINGS,"phase_steps":3,"angle_weight":0.8}, SETTINGS]:
            with self.assertRaises(ValueError):
                validate_output("designer",{"hypothesis":"x","settings":proposal,"rationale":"x"}, evidence)
        result = validate_output("designer",{"hypothesis":"x","settings":{**SETTINGS,"phase_steps":3},"rationale":"x"},evidence)
        self.assertEqual(result["settings"]["phase_steps"],3)
        result = validate_output("designer",{"hypothesis":"x","settings":{**SETTINGS,"controller_version":"v2"},"rationale":"x"},evidence)
        self.assertEqual(result["settings"]["controller_version"],"v2")

    def test_full_trace_diagnostics_do_not_infer_from_samples(self):
        from backend.diagnostics import trace_diagnostics
        trace = [{"reward":v,"contacts":c} for v,c in [(0,0),(0,0),(0,0),(0.5,1),(0.5,0),(0.5,0)]]
        result = trace_diagnostics(trace)
        self.assertEqual(result["longest_no_contact_steps"],3)
        self.assertEqual(result["contact_steps"],1)
        self.assertEqual(result["longest_reward_plateau_steps"],2)

    def test_each_role_has_isolated_session_and_explicit_mapping(self):
        client = Hermes()
        calls = []
        with patch.object(client, "request", side_effect=lambda *args: calls.append(args) or {"run_id": "run_1"}):
            client.start_role("analyst", {"test": 1}, "job1")
            client.start_role("reviewer", {"test": 2}, "job1")
        self.assertEqual(calls[0][0], "/v1/runs")
        self.assertEqual(calls[0][1]["model"], "rx-dev")
        self.assertNotEqual(calls[0][1]["session_id"], calls[1][1]["session_id"])
        self.assertIn("rx-dev-failure-analysis", calls[0][1]["instructions"])
        self.assertIn("rx-dev-evaluation-review", calls[1][1]["instructions"])
        self.assertEqual(calls[0][2]["Idempotency-Key"], calls[0][1]["session_id"])
        self.assertNotIn("key", calls[0][1])

    def test_poll_does_not_restart_after_observation_failure(self):
        client = Hermes()
        responses = [RuntimeError("temporary timeout"), {"status": "running"},
                     {"status": "completed", "output": '{"summary":"ok","findings":[]}'}]
        with patch.object(client, "request", side_effect=responses) as request, patch("backend.hermes.time.sleep"):
            result = client.poll_role("run_same", "analyst", {"seed_split": {"test": [100]}}, lambda _: None, threading.Event())
        self.assertEqual(result["summary"], "ok")
        self.assertEqual([c.args[0] for c in request.call_args_list], ["/v1/runs/run_same"] * 3)

    def test_rejected_designer_output_is_kept_for_local_inspection(self):
        client = Hermes()
        proposal = {"hypothesis": "x", "settings": SETTINGS, "rationale": "x"}
        done = {"status": "completed", "output": json.dumps(proposal)}
        with patch.object(client, "request", return_value=done):
            with self.assertRaises(RejectedOutput) as caught:
                client.poll_role("run_x", "designer", {"selected_settings": SETTINGS, "blocked_settings": []},
                                 lambda _: None, threading.Event())
        self.assertEqual(caught.exception.output, proposal)
        self.assertIn("exactly one", str(caught.exception))

    def test_evidence_is_numerical_and_fresh_seeds_never_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "agent"
            report.mkdir()
            data = {"method": "MPC", "seed_split": {"tuning": [0], "validation": [10], "test": [200]},
                    "step_limit": 300, "selected_settings": SETTINGS,
                    "baseline": {"runs": [{"seed": 200, "video": "private_path"}]},
                    "planner": {"runs": [{"seed": 200, "success": False, "video": "private_path"}]}}
            (report / "report.json").write_text(json.dumps(data))
            evidence = experiment_evidence(report)
            self.assertNotIn("video", evidence["planner"]["runs"][0])
            saved = root / "agents" / "previous"
            saved.mkdir(parents=True)
            (saved / "job.json").write_text(json.dumps({"id": "previous", "status": "completed", "evaluation_seeds": [201, 202]}))
            jobs = AgentJobs(outputs=root, client=object())
            seeds = jobs.reserve_seeds(evidence)
            self.assertEqual(len(seeds), 10)
            self.assertTrue(set(seeds).isdisjoint({0, 10, 200, 201, 202}))


if __name__ == "__main__":
    unittest.main()
