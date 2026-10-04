import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from backend.learning_agents import LearningAgentJobs, measured_comparison, numerical_curve
from backend.learning_protocol import constraints, proposal, request_body, validate_learning_output
from backend.training import TrainingJobs, validate
from backend.hermes import Hermes
from backend.learning_environments import ENVIRONMENTS, environment_of


class LearningChecks(unittest.TestCase):
    def test_learning_roles_receive_separate_sessions_and_actual_skills(self):
        client=Hermes();calls=[]
        with patch.object(client,'request',side_effect=lambda *args:calls.append(args) or {'run_id':'run1'}):
            for role in ('learning_analyst','learning_designer','learning_reviewer'):
                client.start_role(role,{'metric':1},'learning-job')
        self.assertEqual(len({call[1]['session_id'] for call in calls}),3)
        for call,name in zip(calls,('analysis','design','review')):
            self.assertIn(f'rx-dev-learning-{name}',call[1]['instructions'])
            self.assertEqual(call[2]['Idempotency-Key'],call[1]['session_id'])

    def evidence(self, algorithm='act'):
        baseline=validate({'algorithm':algorithm,'steps':128})
        return {'baseline_config':baseline,'allowed_changes':constraints(baseline,128)}

    def test_proposals_preserve_conditions_and_enforce_bounds(self):
        evidence=self.evidence('ppo')
        design={'hypothesis':'lower learning rate','change':{'parameter':'learning_rate','value':.0001},'rationale':'single ablation'}
        candidate=proposal(design,evidence)
        self.assertEqual([k for k in candidate if candidate[k]!=evidence['baseline_config'][k]],['learning_rate'])
        for change in ({'parameter':'seed','value':1}, {'parameter':'batch_size','value':3},
                       {'parameter':'steps','value':256}, {'parameter':'steps','value':65},
                       {'parameter':'gamma','value':float('nan')}, {'parameter':'gamma','value':True}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                proposal({**design,'change':change},evidence)
        with self.assertRaises(ValueError):
            proposal(design,{**evidence,'blocked_changes':[design['change']]})

    def test_legacy_act_and_normalized_rl_config_can_retrain(self):
        legacy={'dataset':'lerobot/pusht','device':'cpu','steps':1,'batch_size':1,'episodes':1,'seed':1}
        self.assertEqual(validate(request_body(legacy))['algorithm'],'act')
        for algorithm in ('act','diffusion','ppo','sac'):
            config=validate({'algorithm':algorithm,'steps':128})
            self.assertEqual(validate(request_body(config)),config)

    def metrics(self, flags):
        seeds=list(range(40000,40000+len(flags)))
        return {'algorithm':'act','input':'pixels_agent_pos','seeds':seeds,'episodes':len(flags),'step_limit':10,
                'runs':[{'seed':seed,'success':flag,'best_reward':.1} for seed,flag in zip(seeds,flags)],
                'success_rate':sum(flags)/len(flags),'mean_best_reward':.1,'wall_seconds':1}

    def test_comparison_uses_matched_outcomes_and_blocks_false_verdict(self):
        base=self.metrics([False,True,False]); candidate=self.metrics([True,False,True])
        comparison=measured_comparison(base,candidate)
        self.assertEqual(comparison['success_gains'],2)
        self.assertEqual(comparison['success_losses'],1)
        self.assertEqual(comparison['measured_verdict'],'improved')
        review={'verdict':'regressed','summary':'','evidence':[],'limitations':[],'next_step':''}
        with self.assertRaises(ValueError):validate_learning_output('learning_reviewer',review,comparison)
        for altered in ({**candidate,'seeds':[1,2,3]}, {**candidate,'success_rate':0}, {**candidate,'runs':list(reversed(candidate['runs']))}):
            with self.assertRaises(ValueError):measured_comparison(base,altered)
        self.assertGreater(comparison['baseline']['success_interval_95'][1],.7)
        with self.assertRaises(ValueError):
            measured_comparison({**base,'environment':'aloha'},{**candidate,'environment':'transfer'})

    def test_environment_contract_selects_datasets_and_blocks_mismatched_sources(self):
        for environment in ('aloha','transfer'):
            imitation=validate({'algorithm':'act','environment':environment,'steps':1})
            self.assertEqual(imitation['dataset'],ENVIRONMENTS[environment]['dataset'])
            self.assertEqual(environment_of({'dataset':imitation['dataset']}),environment)
            reinforcement=validate({'algorithm':'ppo','environment':environment,'steps':128})
            self.assertEqual(validate(request_body(reinforcement)),reinforcement)
            self.assertIsNone(reinforcement['dataset'])
        for body in ({'environment':'unknown'},{'environment':None},{'environment':''},
                     {'environment':'aloha','dataset':'lerobot/pusht'}):
            with self.assertRaises(ValueError):validate(body)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);jobs=TrainingJobs(outputs=root/'training')
            identifier='e'*32;folder=jobs.root/identifier;folder.mkdir()
            config=validate({'algorithm':'ppo','environment':'aloha','steps':128})
            (folder/'job.json').write_text(json.dumps({'id':identifier,'policy':'ppo','status':'completed','config':config}))
            (folder/'model').mkdir();(folder/'model'/'policy.zip').touch()
            with self.assertRaises(ValueError):
                jobs.start({'algorithm':'ppo','environment':'transfer','mode':'resume','source_job':identifier,'steps':128})

    def test_numeric_evidence_excludes_log_text_and_seeds_are_reserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); jobs=TrainingJobs(outputs=root/'training')
            agents=LearningAgentJobs(jobs,outputs=root)
            run=root/'training'/'a'; run.mkdir()
            (run/'run.log').write_text('secret abc\nstep:1 loss:0.25 grdn:1.0 api_key=private\nstep:2 loss:nan\n')
            self.assertEqual(numerical_curve(run,'act'),[{'step':1.,'loss':.25,'grdn':1.}])
            (run/'job.json').write_text(json.dumps({'config':{'seed':40000,'episodes':2},'kind':'evaluation'}))
            saved=agents.folder/'b'; saved.mkdir(parents=True)
            (saved/'job.json').write_text(json.dumps({'evaluation_seeds':[40002],'training_seed':500000}))
            seeds,training_seed=agents.reserve(3)
            self.assertEqual(seeds,[40003,40004,40005]);self.assertEqual(training_seed,500001)

    def test_cancellation_does_not_stop_an_unrelated_training_job(self):
        class Training:
            stopped=False
            def state(self):return {'agent_job':'other'}
            def busy(self):return True
            def stop(self):self.stopped=True
        with tempfile.TemporaryDirectory() as directory:
            training=Training(); agents=LearningAgentJobs(training,outputs=Path(directory))
            agents.current={'id':'own','status':'running'}
            agents.stop();self.assertFalse(training.stopped)
            training.state=lambda:{'agent_job':'own'}
            agents.stop();self.assertTrue(training.stopped)

    def test_recovery_polls_existing_upstream_role_without_resubmission(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); client=Mock()
            client.poll_role.return_value={'summary':'saved execution','findings':[]}
            agents=LearningAgentJobs(Mock(),outputs=root,client=client)
            folder=agents.folder/('f'*32);folder.mkdir(parents=True)
            agents.current={'id':'f'*32,'stage':'learning_analyst','roles':{
                'learning_analyst':{'status':'running','run_id':'existing'}}}
            output=agents.role('learning_analyst',{'metric':1})
            self.assertEqual(output['summary'],'saved execution')
            client.start_role.assert_not_called()
            self.assertEqual(client.poll_role.call_args.args[0],'existing')
            self.assertEqual(agents.role('learning_analyst',{'metric':1}),output)
            self.assertEqual(client.poll_role.call_count,1)
            with self.assertRaises(ValueError):agents.role('learning_analyst',{'metric':2})

    def test_mujoco_workflow_keeps_environment_and_paired_evaluation_conditions(self):
        # Offline role/child fixtures check scheduling; browser checks run real trainers.
        class Training:
            def __init__(self, root):self.root=root;self.calls=[];self.current={'status':'idle'}
            def source(self, identifier):
                if identifier != 'a'*32:
                    return self.root / identifier / 'policy.zip',json.loads((self.root / identifier / 'job.json').read_text())
                return None,{'id':'a'*32,'status':'completed','policy':'ppo',
                             'config':validate({'algorithm':'ppo','environment':'aloha','steps':128})}
            def busy(self):return False
            def history(self):return []
            def state(self):return self.current
            def start(self, body, owner=None):
                self.calls.append(('train',body,owner));return self.finish()
            def evaluate(self, body, seed_start=20000, owner=None):
                self.calls.append(('evaluate',body,owner))
                state=self.finish()
                state['evaluation']={'algorithm':'ppo','environment':'aloha','input':'aloha_joint_object_state',
                  'seeds':list(range(seed_start,seed_start+body['episodes'])),'episodes':body['episodes'],'step_limit':10,'success_rate':0,'mean_best_reward':0,
                  'wall_seconds':1,'runs':[{'seed':seed,'success':False,'best_reward':0,'final_success':False,'first_success_step':None,'steps':1,'sum_reward':0,'final_reward':0} for seed in range(seed_start,seed_start+body['episodes'])]}
                output=self.root/state['id']/'evaluation';output.mkdir()
                for run in state['evaluation']['runs']:
                    (output/f"seed-{run['seed']}.json").write_text(json.dumps([{'step':1,'reward':0,'is_success':False}]))
                (self.root/state['id']/'job.json').write_text(json.dumps(state))
                return state
            def finish(self):
                self.current={'id':f'{len(self.calls):032x}','status':'completed','started_at':1,'finished_at':2}
                folder=self.root/self.current['id'];folder.mkdir()
                (folder/'policy.zip').write_bytes(b'fixture-checkpoint')
                (folder/'job.json').write_text(json.dumps(self.current))
                return self.current
            def detail(self, job):return job
        class Roles:
            def __init__(self):self.inputs=[]
            def health(self):return {'connected':True}
            def start_role(self,role,evidence,job_id):
                self.inputs.append((role,evidence));return {'run_id':'local_'+role}
            def poll_role(self,run_id,role,evidence,progress,cancelled):
                if role=='learning_analyst':return {'summary':'fixture','findings':[]}
                if role=='learning_designer':return {'hypothesis':'fixture','change':{'parameter':'learning_rate','value':.0001},'rationale':'fixture'}
                return {'final_verdict':evidence['decision']['verdict'],'verdict':evidence['measured_verdict'],'summary':'fixture','evidence':[],'limitations':[],'next_step':'fixture'}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);training=Training(root/'training');training.root.mkdir()
            roles=Roles();agents=LearningAgentJobs(training,outputs=root,client=roles)
            agents.start({'source_job':'a'*32,'steps':128,'eval_episodes':1,'step_limit':10})
            agents.worker.join(timeout=5)
            state=agents.state();self.assertEqual(state['status'],'completed',state.get('error'))
            self.assertEqual(len(training.calls),6)
            self.assertTrue(all(body['environment']=='aloha' for kind,body,_ in training.calls if kind=='train'))
            self.assertEqual(state['comparison']['environment'],'aloha')
            self.assertEqual(state['comparison']['simulator']['engine'],'MuJoCo')
            self.assertEqual(state['comparison']['seeds'],state['evaluation_seeds'])
            self.assertEqual([role for role,_ in roles.inputs],['learning_analyst','learning_designer','learning_reviewer'])
            self.assertFalse(set(state['holdout_seeds']) & set(state['evaluation_seeds']))
            self.assertEqual(state['decision']['verdict'],'inconclusive')
            self.assertNotIn('holdout_seeds',roles.inputs[1][1])
            self.assertEqual(len(state['checkpoint_receipts']),2)
            # Simulate a crash after all children finished: no duplicate jobs or role submissions.
            agents.update(status='interrupted')
            restarted=LearningAgentJobs(training,outputs=root,client=roles)
            restarted.resume({'job_id':state['id']});restarted.worker.join(timeout=5)
            self.assertEqual(restarted.state()['status'],'completed',restarted.state().get('error'))
            self.assertEqual(len(training.calls),6)
            self.assertEqual(len(roles.inputs),3)
            # A checkpoint edited after final evaluation must invalidate a resumed experiment.
            restarted.update(status='interrupted')
            (training.root/state['children']['train_candidate']/'policy.zip').write_bytes(b'changed')
            restarted.resume({'job_id':state['id']});restarted.worker.join(timeout=5)
            self.assertEqual(restarted.state()['status'],'failed')
            self.assertIn('checkpoint changed',restarted.state()['error'])


if __name__=='__main__':unittest.main()
