# Learned ACT basket task on macOS LIBERO

All three native MuJoCo episodes recorded on Apple M4 / macOS 26.7 on 2026-10-05.
No local training, scripted actions, changed success predicate or object teleportation.
Fixed benchmark initial states are applied only at reset.

- Task: `libero_object` task 0, `pick_up_the_alphabet_soup_and_place_it_in_the_basket`.
- Public model: https://huggingface.co/rishi264/act-libero-alphabet-soup
- Pinned revision: `4008ed10261d06404d04c04490dc572da2430b7a`.
- Model card: Apache-2.0; 20,000 training updates on 50 demonstrations (7,808 frames).
  Model weights are not bundled. The author's benchmark score is not our result.
- CPU inference with strict checkpoint loading and checkpoint normalization statistics.
- Inputs: two unflipped native 128×128 camera images and official LeRobot 8D robot state.
- Runtime author-recommended temporal ensemble coefficient 0.01 and n_action_steps=1.
- Initialization indices 0, 1, 2; seeds 1000, 1001, 1002; 400 steps each.
- First native success: 144, 145, 147; all final success flags true.
- Each video: 401 frames, 640×480, 20 FPS, 20.05 seconds, including all steps after success.
- Episode JSON: all predicted actions, rewards and native success flags.
- Manifest: checkpoint SHA256 receipts, pinned simulator asset revision, versions,
  full outcomes, trace/video SHA256 receipts and runtime conditions.

Reproduce from repository root:

```sh
sh run_libero_success.sh --policy basket --output outputs/libero-evaluations/basket-new
```

This is one task in three fixed initial conditions, not a generalization score.
The experimental macOS environment is separate from the main app environment.
Source: https://github.com/huggingface/LIBERO
Assets: https://huggingface.co/datasets/lerobot/libero-assets/tree/0b3ea86be5fe169d0fd036ae63d1070ec09e90f6
