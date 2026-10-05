# Actual learned-policy success on macOS LIBERO

Three native MuJoCo executions recorded on Apple M4 / macOS 26.7 on 2026-10-05.
All three episodes are included. No local training, scripted manipulation, replayed
actions, modified success predicate, or object-state teleportation was used.
The benchmark's fixed initial states are applied only during episode reset.

- Task: `libero_goal` task 0, `open_the_middle_drawer_of_the_cabinet`.
- Model: https://huggingface.co/AmberHyunKIM/act_libero_goal_task0
- Model revision: `4db937e8de09123dd9b5707ab7704710000b5f25`.
- Source model trained for 100,000 updates on 43 drawer-task demonstrations;
  license Apache-2.0, per the model card. Model weights are not bundled here.
- Runtime: CPU; ACT `n_action_steps=10`, matching the model author's evaluation
  protocol; official LeRobot LIBERO observation processor and checkpoint stats.
- Fixed initialization indices 0, 1, 2; seeds 1000, 1001, 1002; 300 steps each.
- First native success: 118, 113, 125 respectively. All final success flags true.
- Every video is 301 frames, 640×480, 20 FPS, 15.05 seconds. Recording continues
  after first native success to show the final opened drawer state.
- `episode-*-seed-*.json`: every predicted action, reward and native success flag.
- `manifest.json`: simulator/package versions, checkpoint file SHA256 receipts,
  source asset revision, trace/video SHA256 receipts and all outcomes.
- Independent strict checkpoint loading verified all 234 state-dictionary keys.

Reproduce from the repository root:

```sh
sh run_libero_success.sh --output outputs/libero-evaluations/drawer-new
```

This is evidence of one learned drawer task in three initial conditions, not a
LIBERO benchmark/generalization score or a newly trained local policy. The
experimental macOS environment is separate from the main app environment,
omits Linux EGL probes and keeps NumPy 1.26 for robosuite 1.4 compatibility.

LIBERO source: https://github.com/huggingface/LIBERO
Simulator asset revision:
https://huggingface.co/datasets/lerobot/libero-assets/tree/0b3ea86be5fe169d0fd036ae63d1070ec09e90f6
