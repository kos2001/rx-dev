# Learning experiment harness

This implementation adapts the design principles of [VeriHarness](https://github.com/google-research/veriharness) (Apache-2.0) and [Learn Harness Engineering](https://github.com/walkinglabs/learn-harness-engineering) (MIT). It does not install their runtimes or copy their benchmark skills. VeriHarness verifies general agent artifacts; our adapter verifies measured robot policy evaluations. The resolver and challenger are deterministic local checks, not additional LLM agents. Existing Hermes analysis, design and review roles remain separate sessions.

## Experiment contract

1. Validate the bounded configuration and completed source training record. Save runtime library versions, a training seed and disjoint development/final seed reservations.
2. Analysis and design receive numeric development evidence. Final seeds/outcomes are excluded from their inputs. Permit exactly one bounded configuration change.
3. Retrain baseline and candidate from scratch with the same initialization seed. Record SHA-256 receipts of each checkpoint. These compact pilots are distinct from the parent trained policy.
4. Evaluate development episodes with paired initial conditions. Verify seed order, outcome counts and recomputed mean rewards. Recompute each episode metric from its saved native per-step reward/success trace and preserve trace SHA-256 receipts.
5. Freeze both checkpoints and the proposal. Evaluate both on new final seeds without further tuning. Final results never change the proposal within this experiment.
6. Resolver lists disagreements and candidate regression seeds. Challenger records shared failures, native reward contradictions, peak success that was lost, missing terminal evidence and reward-only gains.
7. Final decision requires consistent evidence, terminal success evidence, more final successes and a two-sided exact paired McNemar/binomial p-value ≤ 0.05. Small samples remain inconclusive. A holdout loss is marked regressed. No automatic model promotion occurs.
8. Independent Hermes review receives the two comparisons and local verification ledger; its development and final verdict fields must match the backend's measured verdicts.

Success rate retains the usual **any native success during an episode** semantics. `final_success` is measured separately. MuJoCo policies continue to the requested horizon after first success to expose drops; PushT stops at native termination. Each evaluator saves per-step native reward/success JSON beside the video. The final decision checks retention among successes in both arms, rather than assuming peak reward implies completion. It does not certify real-world safety. A single training seed and a small finite sample do not establish generalization; repeated experiments have no multiple-comparison correction.

## Persistent state and recovery

`outputs/learning-agents/<id>/job.json` atomically stores stage events, frozen configurations, child IDs, upstream role IDs, checkpoint/evaluation receipts and final decision. Evidence, proposal, role inputs, development comparison, final comparison and verification ledger are separate local JSON artifacts. Runtime outputs are excluded from Git.

`POST /api/learning-agents/resume` with `{"job_id":"<current id>"}` resumes an interrupted/failed/cancelled harness-version-1 experiment when no worker or trainer is active. Completed roles and child jobs are reused. An unfinished upstream role is polled using its existing run ID; no duplicate role is submitted. An incomplete local training/evaluation child restarts **from scratch** with the frozen settings. This is stage recovery, not optimizer continuation. Saved inputs, runtime versions, completed child evidence and checkpoint hashes must remain unchanged. Changed artifacts require a new experiment. A permanently failed/cancelled upstream role may also require a new experiment. Legacy jobs remain viewable but are not resumable.

Cancellation stops only training owned by the current experiment. Each child has a 30-minute limit. Holdout evaluation episodes are bounded at 1–20 per policy (default 10); development at 1–5; horizon at 10–400. Both evaluation phases always run, even if development does not improve.

## UI and verification

The learning screen separates development counts from final verdict, shows Wilson 95% success-rate intervals, exact paired p-value, counterexamples, seed provenance, stage events, linked child records and a recovery button. Existing training history contains the corresponding evaluation videos.

Run local checks:

```sh
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rx-dev-lerobot-venv/bin/python -m unittest discover -s tests -p 'test_*.py'
NODE_PATH=/private/tmp/rx-training-browser/node_modules PLAYWRIGHT_BROWSERS_PATH=/private/tmp/rx-training-browsers node tests/browser_learning_harness.cjs
```

The browser harness test uses explicitly synthetic API responses to check rendering and recovery requests, without provider calls. Unit tests cover false success claims, insufficient samples, success drops, shared failures, checkpoint edits and restart recovery. Actual policy evaluations separately validate simulator execution; short smoke evaluations establish connectivity, not policy competence.

### Local validation (2026-10-05)

- 40 unit/API checks passed, including seed separation, final verdict enforcement, local trace reconciliation, checksum mismatch rejection and recovery without upstream resubmission.
- Desktop/mobile browser checks passed with clearly synthetic API responses, including the recovery POST and training lock.
- Real saved ACT, Diffusion, PPO and SAC policies executed in each of PushT, ALOHA insertion and ALOHA transfer (12 short connectivity evaluations).
- The public pretrained transfer ACT policy additionally completed a full 400-step episode at seed 42000: first native success at step 262, final success true, maximum/final reward 4. This validates the success/retention evaluator, not a new model improvement claim.
- An isolated real MuJoCo PPO workflow ran two 128-step trainings, paired development evaluation (one episode per arm) and separate final evaluation (two episodes per arm). It reconciled six native traces and reused all six completed child jobs after recovery. Its final verdict was inconclusive (p=1). Role responses in this integration check were fixed local fixtures; no new external model call was needed.

## LIBERO task adapter

Two fixed LIBERO tasks now support ACT/Diffusion service training and the same
Agent harness. Demonstrations are filtered to one task from a pinned official
dataset; camera conventions are canonical 256x256, separate from the public
128x128 basket gallery policy. Evaluation pairs fixed benchmark state indices
derived from seeds and rejects overlap between development/final state indices.
Native 7D actions, reward/success and final retention are recorded and checked.
The separate worker's actual package versions participate in recovery checks.
See [LIBERO setup and evidence](libero-learning.md) for the supported scope.
