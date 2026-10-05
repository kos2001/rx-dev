---
name: rx-dev-learning-review
description: Independently review measured paired rx-dev learned-policy evaluations, compute tradeoffs and uncertainty after bounded retraining. Use for simulator learning results, not deployment approval.
---

# Review learned-policy evidence

Use backend success counts and measured_verdict as the numerical verdict.
An increase is improved, a decrease regressed and a tie inconclusive.
Reward or loss changes do not override task success. Cite paired outcomes,
sample count, seeds, input type and episode limit when interpreting results.

Check that simulator and task match. ALOHA insertion and cube transfer
succeed at native reward 4; PushT success is its environment termination
criterion. Keep native reward scales and input privilege distinct.

Review training time separately from inference/evaluation time. Batch and step
changes affect sample exposure; training costs may differ despite common caps.
Check that both arms used the same training seed, data and model structure and
that evaluation seeds are matched. A single training seed and small sample do
not establish statistical significance or robust improvement. Wilson intervals
describe each success rate; they are not a paired significance test.

Pilot models were retrained from scratch. Keep their results separate from
the parent's checkpoint and from longer-run or real-robot performance.
Return the caller's JSON schema with measured evidence, limitations and next
step. Never replace the original checkpoint, change measurements, recommend
retuning on these evaluation seeds as a final holdout, or execute tools.

For LIBERO, keep the single selected manipulation task fixed. Use only the pinned
official dataset episodes for that task: canonical two-camera 256x256 images,
8D robot state and 7D relative actions. Native check_success and reward 1 define
success; first success and final retention are distinct. Compare paired fixed
initial-state indices, not seeds alone; final indices must be disjoint from
development indices. Public gallery scores are not newly trained pilot results.
