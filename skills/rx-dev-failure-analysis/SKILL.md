---
name: rx-dev-failure-analysis
description: Analyze rx-dev PushT failures from measured episode and trace data, distinguishing contact stalls, residual alignment errors and planning randomness. Use for simulator diagnosis, not real-robot safety certification.
---

# PushT failure analysis

Use backend-computed diagnostics as the numerical source of truth. They count
failure categories and complete-trace contact gaps and reward plateaus;
sampled frames alone cannot establish their frequency or duration.

Official termination requires coverage strictly above 0.95. Reward is coverage
divided by 0.95 and clipped, not raw coverage. Cite the actual metric, exact
seed IDs, and whether the result was tuning or evaluation.

Distinguish environment Seed from planner Seed. Do not call a change
nondeterministic unless identical state, settings and planning RNG were repeated
with different outcomes. Different initial conditions can need different contact
strategies even when the implementation is reproducible.

Read experiment_history before recommending another experiment. Identify what
earlier failures rule out and what remains unknown. Do not repeat the same bundled
change or infer individual parameter effects from a multi-parameter experiment.

Return the caller's analyst JSON schema: at most four findings with supported
seed IDs, numerical evidence, and a testable recommendation. No tool execution,
artifact mutation, raw-video transmission or evaluation-seed selection.
