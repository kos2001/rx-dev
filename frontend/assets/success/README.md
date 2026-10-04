# Recorded MuJoCo success examples

These are locally generated simulator recordings, not videos copied from a model card.
Model: https://huggingface.co/lerobot/act_aloha_sim_transfer_cube_human
Revision: `ba73b2766f1371cdc133ca4efb97eb090d744625`.
The model weights are not bundled. Runtime: LeRobot 0.6.1, gym-aloha 0.1.4 and MuJoCo.

Recorded on 2026-10-05 using `backend.pretrained_success --full-rollout`.
Seeds 42000 and 42001 reached native reward 4 and retained `is_success=true`
at step 400; seed 42002 failed. All three recordings are included, each at
50 fps, 640×480, from the simulator's `angle` camera. Poster images are their
actual final frames. `manifest.json` records source and measured outcomes.

This three-episode demonstration is not a generalization benchmark.
