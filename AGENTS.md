# rx-dev development map

- Read `README.md` for setup and supported methods/environments.
- Learning orchestration: `backend/learning_agents.py`; bounded role contracts: `backend/learning_protocol.py`.
- Evidence checks and final decisions: `backend/learning_harness.py`; native policy evaluation: `backend/policy_evaluation.py`.
- Learning UI: `frontend/learning_agents.js`; simulator contracts: `backend/learning_environments.py`.
- Experiment state, recovery semantics and verification commands: `docs/learning-harness.md`.

Keep experiment changes bounded and preserve stored configurations, seeds and checkpoint provenance. Use native simulator outcomes as success evidence; loss reduction, reward alone and short connectivity runs do not establish task success. Keep development and final evaluation inputs separate. Verify backend changes with the tests under `tests/test_*.py`, and screen changes with the relevant browser checks. Describe synthetic fixtures and actual simulator results distinctly. Runtime state lives under `outputs/`; never commit credentials, model weights or raw provider logs. Leave completed steps and recovery information on disk so another session can continue.
