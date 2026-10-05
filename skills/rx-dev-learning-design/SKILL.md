---
name: rx-dev-learning-design
description: Propose one bounded hyperparameter change for rx-dev paired model retraining using explicit learning budgets and prior experiment evidence. Use for ACT, Diffusion, PPO and SAC pilot proposals.
---

# Bounded learning experiment design

Propose one change to baseline_config using allowed_changes. The backend owns
the model family, dataset, compact architecture, devices, seeds and execution.
Keep every other field fixed. Honor blocked_changes and explain how the
proposal relates to measured learning or policy-evaluation evidence.

Keep simulator and task fixed too. A MuJoCo ALOHA pilot must use the
matching demonstration dataset for imitation, or the same joint/object
state and bounded joint-increment controller for reinforcement learning.

For ACT/Diffusion, steps count optimizer updates. For PPO/SAC they count
environment transitions. PPO transitions must align with its rollout interval
and the rollout must divide into allowed minibatches. A SAC pilot needs enough
transitions to pass its initial exploration-only phase.

Changing steps or batch size changes compute and sample exposure. Describe
that tradeoff explicitly. Do not claim a single-parameter change proves a
mechanism or that repeating a parent configuration reproduces its weights.

The backend trains both policies with the same new initialization seed and
evaluates on identical fresh initial-condition seeds. Do not choose or discard
seeds, change algorithms or input privilege, invent a dataset, or promote a
candidate. Return hypothesis, one numeric change and rationale in the supplied
JSON schema. A click authorizes one experiment, not an indefinite search loop.

For LIBERO, keep the single selected manipulation task fixed. Use only the pinned
official dataset episodes for that task: canonical two-camera 256x256 images,
8D robot state and 7D relative actions. Native check_success and reward 1 define
success; first success and final retention are distinct. Compare paired fixed
initial-state indices, not seeds alone; final indices must be disjoint from
development indices. Public gallery scores are not newly trained pilot results.
