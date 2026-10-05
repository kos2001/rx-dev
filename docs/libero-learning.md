# LIBERO service learning and Agent experiments

The service supports two fixed tasks with **ACT and Diffusion imitation learning**:

| Environment | Benchmark task | Official demonstration task index |
|---|---|---|
| `libero_drawer` | LIBERO-Goal 0: open the middle drawer | 19 |
| `libero_basket` | LIBERO-Object 0: alphabet soup into basket | 24 |

Select a task in **학습 & Agents → 학습 환경**. Train a new compact/standard model,
fine-tune a saved service checkpoint, or resume its optimizer. Then evaluate the
checkpoint from the history card. Select a completed training in the Agent form
to run analysis → one-change design → paired training/development evaluation →
frozen final evaluation → independent review. A task switch requires its own model.

## Worker setup

On the verified Apple Silicon Mac:

```sh
sh setup_libero_learning.sh
sh run_app.sh
```

The worker uses `/private/tmp/rx-dev-libero-macos-venv/bin/python`, separately from
the main service environment. Override with `RX_LIBERO_PYTHON` for another worker.
On Linux, install the official LeRobot LIBERO and Diffusion dependencies into a
separate environment and set that variable. Linux service execution is not verified
here. A missing worker is rejected before a job is created. No remote GPU is needed
for CPU execution on the verified Mac. CUDA/MPS availability is checked by the worker.

## Demonstrations and inputs

The [official dataset](https://huggingface.co/datasets/lerobot/libero) is pinned to
`a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4`. Its task table must match the selected
benchmark instruction. The loader reads frame-level episode/task columns and
selects the first N **complete, single-task** episodes (1–40); it rejects mixed-task
episodes and insufficient data. Episode IDs are not assumed contiguous or 0-based
for the selected task. Required video files are fetched before the trainer runs,
and a concrete revision-safe dataset root prevents partial-cache task confusion.

`demonstrations.json` preserves the selected task, episode IDs, dataset revision and
source data hashes beside each training request. Only that selection is passed to
the official LeRobot trainer. The trainer uses real action trajectory timestamps,
its normalizers and checkpoint optimizer state. No synthetic demonstrations or
scripted policy actions are substituted. The service sends no training results to
Hugging Face (`push_to_hub=false`, WandB disabled).

Service inputs are two canonical 256×256 images and an 8D end-effector/gripper state;
outputs are 7D relative pose/gripper actions. The official LIBERO processor flips
both image axes to match the official dataset. This differs from the public basket
gallery checkpoint's unflipped 128×128 training convention. That gallery evaluator
remains separate; its success recordings are not new service-training outcomes.
PPO/SAC are not offered for these LIBERO tasks.

## Native evaluation and Agent evidence

Simulator assets are pinned to `0b3ea86be5fe169d0fd036ae63d1070ec09e90f6`.
A checkpoint loads strictly, and its camera/state/action contract is checked before
execution. ACT replans at most every 10 actions; Diffusion retains its saved action
horizon. Recordings use native agent camera, 640×480, 20 FPS.

A seed selects `seed % 50` from the task's 50 fixed benchmark states. Reset-order
counters do not determine paired initial conditions. For each step, the evaluator
checks the wrapper against native `check_success()` and saves the predicted action,
native reward and success. Execution continues to the requested horizon, including
after first success, to measure final retention. MP4 and trace JSON remain local.

Both Agent pilots train from scratch with the same initialization seed. The designer
can change only one allowed batch/step parameter; simulator, task, demonstrations,
algorithm, architecture and input privilege stay fixed. Final state indices must be
disjoint from development state indices. Native trace reconciliation, frozen
checkpoint hashes, paired uncertainty, retention and failure checks gate the final
verdict. No automatic promotion occurs. Benchmark demonstrations may cover these
states; disjoint evaluation phases do not establish unseen-task generalization.

Each role uses the updated `rx-dev-learning-analysis`, `rx-dev-learning-design` or
`rx-dev-learning-review` skill in an isolated Hermes session. Numeric settings and
metrics are sent to the configured model provider; videos, weights and raw trainer
logs remain local. Interrupted experiments reuse completed stages only if worker
versions, checkpoint receipts and saved evidence still match.

## Verification

Synthetic contract tests: `tests/test_libero_learning.py`. They cover mixed-task
rejection, unsupported settings, missing workers, seed-to-state pairing and native
trace contradictions. Existing harness tests cover frozen checkpoints and recovery.
Browser checks: `tests/browser_libero_learning.cjs` (real saved records, no training
or provider submissions) and existing learning, education and success-gallery checks.
Actual execution evidence is recorded separately under `outputs/libero-service-validation/`.
Short training/evaluation runs verify integration and do not establish learned task
success. The public success gallery remains labeled as pretrained-policy evidence.

### Actual local validation — 2026-10-05

- ACT drawer job `85d54b1086764a10bc3bc65d00662ad5`: one real optimizer update,
  batch 1, official demonstration episode 399; checkpoint saved and evaluated.
- Diffusion basket job `67a266b91fa14da0b3ee3da34cb0cb4a`: one real optimizer
  update, batch 1, official demonstration episode 813; checkpoint saved and evaluated.
- Both native evaluations recorded 20 steps, 21 video frames, 7D predicted actions,
  binary native reward/success and final success false. These are connectivity checks.
- ACT optimizer continuation reached total update 2 in job
  `e68de65e58ac44bebf31f6a31ad01a57`.
- Diffusion optimizer continuation reached total update 2 in job
  `0b9d03307b6e4a3585dd97fdda616b34` with the pinned Diffusers 0.39 worker.
- **Actual Hermes workflow** `752aed93d4a54c9fa46156de23a39a6b` completed analysis,
  design and independent review in three separate upstream runs. The proposed
  single change was batch 1 → 4, with one update per newly initialized ACT pilot.
  Training seed 500002; development seed 40002/state 2; final seed 40003/state 3.
  Both arms had 0/1 success in each phase. Four native evaluation traces reconciled;
  final result `inconclusive`, exact paired p=1, no automatic promotion.
- These are measured local executions, not synthetic role responses. They verify
  the integrated service path, not a claim that a one-update pilot learned the task.
  Runtime requests, checkpoints, MP4s and full evidence remain under `outputs/`.
