# Actual macOS LIBERO portability smoke

Recorded locally on Apple M4 / macOS 26.7, 2026-10-05, using
`backend/libero_probe.py`. This is an untrained zero-end-effector-motion
control with open gripper, not a learned-policy evaluation or task success.

- LIBERO-Spatial task 0, seed 1000, 60 control steps, 61 frames at 20 FPS.
- Native success: false. Raw measured values are in `trace.json`.
- Versions, task BDDL digest, video digest and asset revision: `result.json`.
- Source: https://github.com/huggingface/LIBERO (`hf-libero` 0.1.4).
- Simulator assets: https://huggingface.co/datasets/lerobot/libero-assets/tree/0b3ea86be5fe169d0fd036ae63d1070ec09e90f6
- Reproduce via `sh run_libero_probe.sh` from the repository root.

The experimental environment omits Linux-only EGL device probes and uses
robosuite's existing macOS GLFW/CGL rendering path. The official LeRobot
LIBERO extra still targets Linux. This smoke does not validate all LIBERO
tasks or enable LIBERO policy training/evaluation in the service.
