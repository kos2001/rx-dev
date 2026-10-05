"""Synthetic contract checks; actual simulator checks are recorded separately."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.training import TrainingJobs, validate
from backend.libero_training import task_episode_ids
from backend.libero_runtime import initial_state_index
from backend.learning_harness import evidence_ledger, verify_episode_traces


class LiberoLearningContracts(unittest.TestCase):
    def test_fixed_task_and_method_validation(self):
        for environment in ('libero_drawer', 'libero_basket'):
            for algorithm in ('act', 'diffusion'):
                self.assertEqual(validate({'environment':environment,'algorithm':algorithm})['dataset'],'lerobot/libero')
            for extra in ({'dataset':'lerobot/pusht'}, {'dataset':'user/other'}, {'algorithm':'ppo'}, {'algorithm':'sac'}, {'episodes':41}, {'episodes':'1'}):
                with self.subTest(extra=extra), self.assertRaises(ValueError):
                    validate({'environment':environment, **extra})

    def test_demonstrations_are_whole_single_task_episodes(self):
        rows=[(9,19),(9,19),(10,24),(10,24),(11,19),(11,24),(12,19)]
        self.assertEqual(task_episode_ids(rows,19,2),[9,12])
        self.assertEqual(task_episode_ids(rows,24,1),[10])
        with self.assertRaises(ValueError):task_episode_ids(rows,19,3)

    def test_unavailable_worker_fails_before_job_creation(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ',{'RX_LIBERO_PYTHON':folder+'/missing'}):
            jobs=TrainingJobs(outputs=folder)
            with self.assertRaises(ValueError):jobs.start({'environment':'libero_drawer'})
            self.assertEqual(list(Path(folder).glob('*/job.json')),[])

    def test_paired_and_disjoint_benchmark_initial_states(self):
        development=[initial_state_index(seed,50) for seed in range(40048,40051)]
        final=[initial_state_index(seed,50) for seed in range(40051,40071)]
        self.assertFalse(set(development)&set(final))
        baseline={'environment':'libero_drawer','runs':[{'seed':40048,'success':False,'final_success':False,'best_reward':0,'init_state_index':48}], 'mean_best_reward':0}
        candidate={**baseline,'runs':[dict(baseline['runs'][0])]}
        comparison={'pairs':[{'seed':40048,'baseline_success':False,'candidate_success':False}],'success_gains':0,'success_losses':0,'baseline':{'successes':0,'mean_best_reward':0},'candidate':{'successes':0,'mean_best_reward':0}}
        self.assertTrue(evidence_ledger(baseline,candidate,comparison)['valid'])
        candidate['runs'][0]['init_state_index']=49
        self.assertFalse(evidence_ledger(baseline,candidate,comparison)['valid'])

    def test_libero_trace_rejects_false_reward_and_invalid_action(self):
        run={'seed':1,'success':True,'final_success':True,'first_success_step':1,'steps':1,'best_reward':1,'sum_reward':1,'final_reward':1}
        metrics={'environment':'libero_basket','runs':[run]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'seed-1.json'
            trace=[{'step':1,'reward':1,'is_success':True,'action':[0]*7}]
            path.write_text(json.dumps(trace))
            self.assertEqual(len(verify_episode_traces(metrics,folder)),1)
            trace[0]['action']=[0]*6;path.write_text(json.dumps(trace))
            with self.assertRaises(ValueError):verify_episode_traces(metrics,folder)
            trace[0].update(action=[0]*7,reward=0);path.write_text(json.dumps(trace))
            run.update(best_reward=0,sum_reward=0,final_reward=0)
            with self.assertRaises(ValueError):verify_episode_traces(metrics,folder)
