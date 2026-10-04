import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.learning_agents import measured_comparison
from backend.learning_harness import checkpoint_receipt, evidence_ledger, final_decision, paired_p_value, verify_episode_traces
from backend.policy_evaluation import record_policy


def metrics(flags, seed=60000, final=None):
    final = flags if final is None else final
    runs = [{'seed': seed+i, 'success': success, 'final_success': final[i], 'best_reward': 4 if success else 0}
            for i, success in enumerate(flags)]
    return {'algorithm': 'act', 'environment': 'transfer', 'input': 'pixels_agent_pos',
            'seeds': [r['seed'] for r in runs], 'episodes': len(runs), 'step_limit': 400,
            'runs': runs, 'success_rate': sum(flags)/len(flags),
            'mean_best_reward': sum(r['best_reward'] for r in runs)/len(runs), 'wall_seconds': 1}


class HarnessChecks(unittest.TestCase):
    def decision(self, baseline, candidate):
        comparison = measured_comparison(baseline, candidate)
        ledger = evidence_ledger(baseline, candidate, comparison)
        return final_decision(comparison, comparison, ledger), ledger

    def test_small_count_gain_is_not_verified_improvement(self):
        decision, _ = self.decision(metrics([False]*3), metrics([True]*3))
        self.assertEqual(decision['verdict'], 'inconclusive')
        self.assertEqual(decision['paired_p_value'], .25)
        decision, _ = self.decision(metrics([False]*10), metrics([True]*10))
        self.assertEqual(decision['verdict'], 'verified_improvement')
        self.assertFalse(decision['automatic_promotion'])
        self.assertEqual(paired_p_value(0, 0), 1)
        self.assertEqual(paired_p_value(4, 4), 1)

    def test_peak_success_without_retention_blocks_verification(self):
        decision, ledger = self.decision(metrics([False]*10), metrics([True]*10, final=[False]*10))
        self.assertEqual(decision['verdict'], 'inconclusive')
        self.assertEqual(len(ledger['challenger']['retention_failures']), 10)
        candidate = metrics([True]*10)
        for run in candidate['runs']:
            run.pop('final_success')
        decision, ledger = self.decision(metrics([False]*10), candidate)
        self.assertEqual(decision['verdict'], 'inconclusive')
        self.assertEqual(len(ledger['challenger']['missing_terminal_evidence']), 10)

    def test_native_reward_contradiction_invalidates_evidence(self):
        candidate = metrics([True]*3)
        candidate['runs'][0]['best_reward'] = 0
        candidate['mean_best_reward'] = 8/3
        decision, ledger = self.decision(metrics([False]*3), candidate)
        self.assertEqual(decision['verdict'], 'invalid_evidence')
        self.assertFalse(ledger['valid'])

    def test_reviewer_cannot_override_final_verification(self):
        from backend.learning_protocol import validate_learning_output
        evidence={'measured_verdict':'improved','decision':{'verdict':'inconclusive'}}
        output={'verdict':'improved','final_verdict':'verified_improvement','summary':'',
                'evidence':[],'limitations':[],'next_step':''}
        with self.assertRaises(ValueError):validate_learning_output('learning_reviewer',output,evidence)
        output['final_verdict']='inconclusive'
        self.assertEqual(validate_learning_output('learning_reviewer',output,evidence),output)

    def test_disagreement_and_shared_failure_have_specific_seeds(self):
        _, ledger = self.decision(metrics([True,False,False]), metrics([False,True,False]))
        self.assertEqual(ledger['resolver']['regression_seeds'], [60000])
        self.assertEqual(ledger['challenger']['shared_failure_seeds'], [60002])

    def test_frozen_checkpoint_receipt_detects_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory)/'policy.zip'
            file.write_bytes(b'original')
            original = checkpoint_receipt(file)
            file.write_bytes(b'edited')
            self.assertNotEqual(original, checkpoint_receipt(file))

    def test_full_rollout_measures_success_then_drop_with_native_trace(self):
        class Env:
            closed = False
            def reset(self, seed): self.step_index=0;return 0, {}
            def step(self, action):
                self.step_index += 1
                return 0, 4 if self.step_index == 1 else 0, self.step_index == 1, self.step_index == 3, {'is_success':self.step_index == 1}
            def close(self):self.closed=True
        class Writer:
            def __enter__(self):return self
            def __exit__(self, *args):pass
            def append_data(self, frame):pass
        env=Env();env.unwrapped=env;env._env=env;env.physics=env;env.render=lambda **kw:None
        with tempfile.TemporaryDirectory() as directory, patch('imageio.v2.get_writer',return_value=Writer()):
            result=record_policy({'environment':'transfer','seed':1,'episodes':1,'step_limit':3},env,lambda obs:0,lambda:None,Path(directory))
            run=result['runs'][0]
            self.assertTrue(run['success']);self.assertFalse(run['final_success'])
            self.assertEqual(run['steps'],3);self.assertEqual(run['first_success_step'],1)
            self.assertTrue((Path(directory)/'seed-1.json').is_file())
            self.assertTrue(env.closed)
            result['environment']='transfer'
            self.assertEqual(len(verify_episode_traces(result,Path(directory))),1)
            run['final_success']=True
            with self.assertRaises(ValueError):verify_episode_traces(result,Path(directory))
