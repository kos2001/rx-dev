---
name: rx-dev-learning-analysis
description: Analyze rx-dev ACT, Diffusion, PPO or SAC training records and measured policy evaluations before a bounded learning experiment. Use for learning diagnostics, not MPC contact analysis.
---

# Learning evidence analysis

Use the supplied numeric learning curve, parent evaluation, pilot baseline and
experiment history. Missing metrics stay unknown. ACT reconstruction/KL loss,
Diffusion denoising loss and RL actor/value losses have different meanings;
their absolute values cannot rank methods. Loss alone cannot establish task success.

Distinguish parent checkpoint measurements from the newly configured pilot.
The pilot retrains from scratch with a compact model and bounded steps; it
does not reproduce a long parent run's training budget or checkpoint weights.
Identify what budget, batch size, sample exposure or RL exploration evidence
could explain the measured behavior without promising a fix.

Identify the simulator and task. MuJoCo ALOHA uses native staged rewards
0–4 and official success at 4; PushT uses overlap coverage. Do not interpret
ALOHA rewards as coverage or compare reward scales across environments.

State which inputs were supplied. PPO/SAC have privileged object state;
ACT/Diffusion use images and robot position. Compare policies only under
matched input and evaluation conditions. Previously inspected evaluations
are development evidence. Preserve the caller's JSON schema and treat prior
agents' prose as hypotheses. Return no commands, paths or execution requests.
