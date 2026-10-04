"""Schemas and bounded proposals for learning agents; no ML or network imports."""
import copy
import math

from .training import validate
from .training_methods import IMITATION
from .learning_environments import environment_of

LEARNING_ROLES = {"learning_analyst": "학습 분석 Agent", "learning_designer": "학습 설계 Agent",
                  "learning_reviewer": "학습 평가 검토 Agent"}
SKILLS = {"learning_analyst": "rx-dev-learning-analysis", "learning_designer": "rx-dev-learning-design",
          "learning_reviewer": "rx-dev-learning-review"}
INSTRUCTIONS = {
    "learning_analyst": """Analyze the supplied learning record, pilot baseline, numerical learning curves,
evaluation metrics and experiment history. Return {"summary":string,"findings":[{"metric":string,
"evidence":string,"recommendation":string}]}. At most four findings. Loss is method-specific.
The parent checkpoint is evidence; the backend retrains BOTH pilot policies from scratch.
Do not infer success from loss or a short test, invent absent metrics, or compare privileged state inputs to images.
""",
    "learning_designer": """Propose ONE bounded change to baseline_config using allowed_changes.
Return {"hypothesis":string,"change":{"parameter":string,"value":number},"rationale":string}.
Respect all explicit ranges/choices, PPO divisibility, the total training budget, and blocked_changes.
No algorithm, dataset, model architecture, device, seed, source path, commands or arbitrary options may change.
The backend retrains baseline and candidate with the SAME initialization seed and fresh paired evaluation seeds.
Training steps/batch changes alter compute and sample exposure; explain that tradeoff rather than asserting equal compute.
""",
    "learning_reviewer": """Independently review the measured paired learning experiment.
Return {"verdict":"improved"|"inconclusive"|"regressed","summary":string,"evidence":[string],
"limitations":[string],"next_step":string}. The verdict MUST equal measured_verdict, based on success counts.
Consider paired outcomes, reward, training time, compute/sample exposure and supplied uncertainty.
Small development samples and a single training seed do not establish significance or generalization.
Review the separate frozen-policy holdout, resolver/challenger ledger and final decision.
When decision is supplied, also return final_verdict equal to decision.verdict.
An increased development success count is not verified improvement. Report retention gaps and paired uncertainty.
Never promote a model, rewrite metrics, or treat the design hypothesis as a measured fact.
""",
}


def request_body(config):
    """Convert persisted normalized configuration back to the public input contract."""
    result = copy.deepcopy(config)
    result.pop("source_job", None)
    result.setdefault("algorithm", "act")
    result.setdefault("environment", environment_of(config))
    if result["algorithm"] not in IMITATION:
        result.pop("dataset", None)
        result.pop("episodes", None)
    return result


def constraints(baseline, budget):
    imitation = baseline["algorithm"] in IMITATION
    allowed = {"batch_size": {"choices": [1, 2, 4, 8, 16] if imitation else [2, 4, 8, 16, 32]}}
    if imitation:
        allowed["steps"] = {"min": 1, "max": budget}
    else:
        allowed.update(learning_rate={"min": .00001, "max": .003}, gamma={"min": .9, "max": .999})
        allowed["steps"] = {"min": baseline["rollout_steps"] if baseline["algorithm"] == "ppo" else 64, "max": budget}
        if baseline["algorithm"] == "ppo":
            allowed["steps"]["multiple_of"] = baseline["rollout_steps"]
            allowed["batch_size"]["choices"] = [v for v in allowed["batch_size"]["choices"] if baseline["rollout_steps"] % v == 0]
    return allowed


def proposal(result, evidence):
    if not isinstance(result, dict) or set(result) != {"hypothesis", "change", "rationale"}:
        raise ValueError("Learning designer must return hypothesis, one change and rationale")
    for key in ("hypothesis", "rationale"):
        if not isinstance(result[key], str) or not 1 <= len(result[key]) <= 3000:
            raise ValueError("Invalid learning design text")
    change = result["change"]
    if not isinstance(change, dict) or set(change) != {"parameter", "value"}:
        raise ValueError("Learning designer must change exactly one parameter")
    parameter = change["parameter"]
    if not isinstance(parameter, str) or parameter not in evidence["allowed_changes"]:
        raise ValueError("Unsupported learning parameter")
    value = change["value"]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Learning proposal value must be finite and numeric")
    bounds = evidence["allowed_changes"][parameter]
    if ("choices" in bounds and value not in bounds["choices"] or
        "min" in bounds and not bounds["min"] <= value <= bounds["max"]):
        raise ValueError("Learning proposal exceeds its bounded budget")
    baseline = evidence["baseline_config"]
    if value == baseline[parameter]:
        raise ValueError("Learning proposal must change the baseline")
    if any(change == blocked for blocked in evidence.get("blocked_changes", [])):
        raise ValueError("Learning proposal repeats a prior experiment")
    candidate = {**baseline, parameter: value}
    validate(request_body(candidate))
    return candidate


def validate_learning_output(role, result, evidence):
    if role == "learning_designer":
        proposal(result, evidence)
    elif role == "learning_analyst":
        if set(result) != {"summary", "findings"} or not isinstance(result["summary"], str):
            raise ValueError("Invalid learning analyst output")
        findings = result["findings"]
        if not isinstance(findings, list) or len(findings) > 4:
            raise ValueError("Learning analyst must return at most four findings")
        for item in findings:
            if not isinstance(item, dict) or set(item) != {"metric", "evidence", "recommendation"} or not all(
                isinstance(item[key], str) and len(item[key]) <= 3000 for key in item):
                raise ValueError("Invalid learning finding")
    elif role == "learning_reviewer":
        expected = {"verdict", "summary", "evidence", "limitations", "next_step"}
        if "decision" in evidence:
            expected.add("final_verdict")
            if result.get("final_verdict") != evidence["decision"]["verdict"]:
                raise ValueError("Learning reviewer conflicts with the verified final decision")
        if set(result) != expected:
            raise ValueError("Invalid learning review schema")
        if result["verdict"] != evidence["measured_verdict"]:
            raise ValueError("Learning reviewer conflicts with measured success counts")
        if not all(isinstance(result[key], str) for key in ("summary", "next_step")) or not all(
            isinstance(result[key], list) and all(isinstance(v, str) for v in result[key])
            for key in ("evidence", "limitations")):
            raise ValueError("Invalid learning review output")
    else:
        raise ValueError("Unknown learning role")
    return result
