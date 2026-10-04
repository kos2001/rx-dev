---
name: rx-dev-evaluation-review
description: Review rx-dev paired simulator evaluations for success, reward, runtime, seed separation and statistical uncertainty. Use for controller experiment acceptance, not real-world deployment approval.
---

# Paired simulation review

Treat measurements as evidence and designer prose as a hypothesis. Respect the
backend measured_verdict but distinguish a numerical win from statistical support.
Explain equal-success cases with lower reward or higher computational cost.

Check equal environment seeds, planner seeds, step limits and initial states.
Separate prediction cost from official success. Verify rerenders against outcomes,
but do not substitute recording time for controller runtime.

Report counts with denominators, paired reward wins/losses, runtime and confidence
intervals when supplied. Episodes or independent initial conditions are the units,
not video frames. Small samples and repeated candidate selection do not prove
generalization. A tuned winner needs an untouched final test suite.

Return the caller's reviewer schema. State supported claims, inconclusive claims,
and the smallest useful next test. No real-robot deployment or automatic adoption
from simulator-only evidence.
