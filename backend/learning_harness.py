"""Evidence-driven checks adapted from VeriHarness; no model or network calls.

Resolver checks differing outcomes; challenger checks shared failure, reward-only
claims and missing terminal evidence. Simulator measurements remain authoritative.
"""
import hashlib
import importlib.metadata
import math
from pathlib import Path


def checkpoint_receipt(checkpoint):
    checkpoint = Path(checkpoint)
    files = sorted(checkpoint.rglob('*')) if checkpoint.is_dir() else [checkpoint]
    records = []
    for path in files:
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            records.append({'file': path.relative_to(checkpoint).as_posix() if checkpoint.is_dir() else path.name,
                            'sha256': digest.hexdigest(), 'bytes': path.stat().st_size})
    if not records:
        raise ValueError('Checkpoint has no verifiable files')
    return records


def runtime_versions(environment=None):
    if environment and environment.startswith('libero_'):
        import json
        import subprocess
        from .libero_runtime import worker_python
        names = ('lerobot', 'hf-libero', 'robosuite', 'mujoco', 'numpy', 'torch', 'torchvision', 'gymnasium', 'diffusers')
        code = 'import importlib.metadata as m, json; print(json.dumps({n:m.version(n) for n in ' + repr(names) + '}))'
        result = subprocess.run([worker_python(), '-c', code], capture_output=True, text=True, check=True, timeout=15)
        return {'worker': worker_python(), **json.loads(result.stdout)}
    versions = {}
    for name in ('lerobot', 'gymnasium', 'gym-aloha', 'gym-pusht', 'mujoco', 'torch', 'stable-baselines3'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def paired_p_value(gains, losses):
    """Two-sided exact McNemar/binomial test on discordant paired outcomes."""
    n = gains + losses
    return min(1., 2 * sum(math.comb(n, k) for k in range(min(gains, losses) + 1)) / 2**n) if n else 1.


def evidence_ledger(baseline, candidate, comparison):
    issues, limitations, terminal = [], [], []
    failures, losses, shared_failures = [], [], []
    for arm, metrics in (('baseline', baseline), ('candidate', candidate)):
        for run in metrics['runs']:
            seed = run['seed']
            reward = run['best_reward']
            if type(reward) not in (int, float) or not math.isfinite(reward):
                issues.append(f'{arm}:{seed}: non-finite reward')
            if metrics.get('environment') in ('aloha', 'transfer') and run['success'] and reward != 4:
                issues.append(f'{arm}:{seed}: success contradicts native reward 4')
            if metrics.get('environment', '').startswith('libero_') and run['success'] and reward != 1:
                issues.append(f'{arm}:{seed}: success contradicts native LIBERO reward 1')
            final = run.get('final_success')
            if run['success'] and final is False:
                failures.append({'arm': arm, 'seed': seed, 'reason': 'success_not_retained'})
            if run['success'] and type(final) is not bool:
                terminal.append({'arm': arm, 'seed': seed})
    if baseline.get('environment', '').startswith('libero_'):
        left = [run.get('init_state_index') for run in baseline['runs']]
        right = [run.get('init_state_index') for run in candidate['runs']]
        if left != right or any(type(index) is not int for index in left) or len(set(left)) != len(left):
            issues.append('LIBERO paired initial states are missing, unmatched or repeated')
    for pair in comparison['pairs']:
        if pair['baseline_success'] and not pair['candidate_success']:
            losses.append(pair['seed'])
        if not pair['baseline_success'] and not pair['candidate_success']:
            shared_failures.append(pair['seed'])
    if terminal:
        limitations.append('Some successful episodes lack terminal success evidence; retention is unverified.')
    limitations.append('One training seed; conclusions apply only to these policies and this evaluation sample.')
    return {'resolver': {'success_gains': comparison['success_gains'], 'success_losses': comparison['success_losses'],
                         'regression_seeds': losses, 'pairs': comparison['pairs']},
            'challenger': {'shared_failure_seeds': shared_failures, 'retention_failures': failures,
                           'missing_terminal_evidence': terminal,
                           'reward_only_improvement': comparison['candidate']['mean_best_reward'] > comparison['baseline']['mean_best_reward']
                           and comparison['candidate']['successes'] <= comparison['baseline']['successes']},
            'issues': issues, 'limitations': limitations, 'valid': not issues,
            'retention_verified': not failures and not terminal}


def final_decision(development, holdout, ledger):
    p = paired_p_value(holdout['success_gains'], holdout['success_losses'])
    verified = ledger['valid'] and ledger['retention_verified'] and holdout['measured_verdict'] == 'improved' and p <= .05
    return {'verdict': 'verified_improvement' if verified else 'invalid_evidence' if not ledger['valid'] else
            'regressed' if holdout['measured_verdict'] == 'regressed' else 'inconclusive',
            'paired_p_value': p, 'alpha': .05, 'development_verdict': development['measured_verdict'],
            'holdout_verdict': holdout['measured_verdict'], 'automatic_promotion': False,
            'scope': 'Single frozen candidate, fresh holdout episodes, one training seed; no generalization claim.'}


def verify_episode_traces(metrics, folder):
    """Recompute outcomes from local native episode evidence, not an Agent's claims."""
    import json
    receipts = []
    for run in metrics['runs']:
        path = Path(folder) / f"seed-{run['seed']}.json"
        trace = json.loads(path.read_text())
        if not trace or any(point['step'] != index + 1 or type(point['is_success']) is not bool
                            or type(point['reward']) not in (int, float) or not math.isfinite(point['reward'])
                            for index, point in enumerate(trace)):
            raise ValueError('Native episode trace is invalid')
        successes = [point['step'] for point in trace if point['is_success']]
        rewards = [point['reward'] for point in trace]
        if (run['success'] != bool(successes) or run['final_success'] != trace[-1]['is_success']
            or run['first_success_step'] != (successes[0] if successes else None)
            or run['steps'] != len(trace) or not math.isclose(run['best_reward'], max(rewards))
            or not math.isclose(run['sum_reward'], sum(rewards))
            or not math.isclose(run['final_reward'], rewards[-1])):
            raise ValueError('Episode metrics contradict native trace evidence')
        if metrics.get('environment') in ('aloha', 'transfer') and any(point['is_success'] != (point['reward'] == 4) for point in trace):
            raise ValueError('Trace success contradicts native MuJoCo reward')
        if metrics.get('environment', '').startswith('libero_'):
            if any(point['is_success'] != (point['reward'] == 1) or len(point.get('action', [])) != 7 or any(not math.isfinite(v) for v in point['action']) for point in trace):
                raise ValueError('Trace contradicts native LIBERO action/reward contract')
        receipts.extend(checkpoint_receipt(path))
    return receipts
