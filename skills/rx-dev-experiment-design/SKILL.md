---
name: rx-dev-experiment-design
description: Design bounded one-change PushT controller ablations for rx-dev using prior measured experiments and full-trace diagnostics. Use for simulator proposals, not autonomous hardware deployment.
---

# PushT experiment design

Read diagnostics and experiment_history first. Change exactly one canonical
setting from the incumbent; absent controller_version means v1. A version change
is a structural ablation, not an individual parameter effect. Keep every other
setting identical. The backend enforces this and checks supported bounds.

Do not repeat normalized settings in blocked_settings. Earlier unsuccessful
experiments are evidence, not a reason to request an identical experiment.

Tie the hypothesis to measured failures: contact recovery for verified no-contact
plateaus, shorter replanning for drift, or the official coverage objective for
terminal alignment. More candidates, horizon or steps is a compute-budget tradeoff,
not proof of better control. Respect the supplied supported controller versions.

Hold environment and planner randomness apart. The backend owns disjoint Seed
reservation and equal budgets. Test results used to design a change are development
evidence thereafter. Never select, discard or retune on evaluation seeds.

Return the caller's designer schema: one hypothesis, one complete settings object
and an attributable rationale. No commands, arbitrary code, credentials, external
services, automatic incumbent replacement or pre-execution improvement claims.
