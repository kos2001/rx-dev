"""Evaluate a pinned public ACT policy on its LIBERO drawer task in native MuJoCo."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

from .libero_probe import ASSET_REVISION

MODEL = 'AmberHyunKIM/act_libero_goal_task0'
MODEL_REVISION = '4db937e8de09123dd9b5707ab7704710000b5f25'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='outputs/pretrained/act-libero-goal-task0')
    parser.add_argument('--output', required=True)
    parser.add_argument('--episodes', type=int, default=3)
    parser.add_argument('--steps', type=int, default=300)
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--device', choices=['cpu', 'mps'], default='cpu')
    args = parser.parse_args()
    if not 1 <= args.episodes <= 10 or not 50 <= args.steps <= 400:
        parser.error('episodes must be 1..10 and steps 50..400')
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    os.environ['LIBERO_CONFIG_PATH'] = str(folder / 'config')
    os.environ['HF_HOME'] = str(folder.parent / 'hf-cache')
    os.environ['TORCH_HOME'] = str(folder.parent / 'torch-cache')
    os.environ['MPLCONFIGDIR'] = str(folder / 'matplotlib')
    os.environ['NUMBA_CACHE_DIR'] = str(folder / 'numba')
    os.environ['MUJOCO_GL'] = 'cgl' if sys.platform == 'darwin' else 'egl'
    report = {'status': 'started', 'learned_policy': True, 'local_training': False,
              'model': MODEL, 'model_revision': MODEL_REVISION, 'asset_revision': ASSET_REVISION,
              'host': platform.platform(), 'architecture': platform.machine(), 'config': vars(args),
              'suite': 'libero_goal', 'task_id': 0, 'runs': [],
              'success_rule': 'native LIBERO env.check_success(); first and final success separately',
              'continue_after_first_success': True, 'control_freq': 20, 'video_fps': 20,
              'runtime_policy_overrides': {'device': args.device, 'n_action_steps': 10, 'backbone_initialization_weights': None},
              'packages': {name: importlib.metadata.version(name) for name in ['lerobot', 'hf-libero', 'robosuite', 'mujoco', 'numpy', 'torch']}}
    start = time.monotonic()
    env = None

    def save():
        report['seconds'] = time.monotonic() - start
        (folder / 'results.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')

    try:
        import numpy as np
        import torch
        import yaml
        import imageio.v2 as imageio
        from huggingface_hub import snapshot_download
        torch.set_num_threads(4)
        model = Path(args.model).resolve()
        snapshot_download(MODEL, revision=MODEL_REVISION, local_dir=str(model))
        report['model_files'] = {p.name: digest(p) for p in model.iterdir() if p.is_file()}
        root = Path(next(iter(importlib.util.find_spec('libero').submodule_search_locations))) / 'libero'
        assets = Path('outputs/platform-probes/libero-assets').resolve()
        snapshot_download('lerobot/libero-assets', repo_type='dataset', revision=ASSET_REVISION, local_dir=str(assets))
        config_folder = folder / 'config'
        config_folder.mkdir()
        config = {'benchmark_root': str(root), 'bddl_files': str(root / 'bddl_files'),
                  'init_states': str(root / 'init_files'), 'datasets': str(folder / 'datasets'), 'assets': str(assets)}
        (config_folder / 'config.yaml').write_text(yaml.safe_dump(config))
        import libero.libero as libero_module
        libero_module._assets_path_cache = str(assets)
        from libero.libero import benchmark
        from lerobot.envs.libero import LiberoEnv
        from lerobot.envs.utils import preprocess_observation
        from lerobot.processor import LiberoProcessorStep, PolicyProcessorPipeline
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.act.modeling_act import ACTPolicy
        from lerobot.policies.factory import make_pre_post_processors
        cfg = ACTConfig.from_pretrained(model)
        cfg.device = args.device
        cfg.n_action_steps = 10  # Matches the model author's published evaluation protocol.
        cfg.pretrained_backbone_weights = None  # Every learned backbone weight is loaded from the checkpoint.
        print('Loading pinned ACT policy', flush=True)
        policy = ACTPolicy.from_pretrained(model, config=cfg, strict=True).to(args.device).eval()
        pre, post = make_pre_post_processors(cfg, pretrained_path=model,
                    preprocessor_overrides={'device_processor': {'device': args.device}})
        env_pre = PolicyProcessorPipeline(steps=[LiberoProcessorStep()])
        suite = benchmark.get_benchmark_dict()['libero_goal']()
        task = suite.get_task(0)
        if task.name != 'open_the_middle_drawer_of_the_cabinet':
            raise ValueError('Pinned single-task checkpoint requires the middle drawer task')
        report['task_name'], report['task_language'] = task.name, task.language
        report['bddl_sha256'] = digest(root / 'bddl_files' / task.problem_folder / task.bddl_file)
        report['init_states_sha256'] = digest(root / 'init_files' / task.problem_folder / task.init_states_file)
        env = LiberoEnv(suite, 0, 'libero_goal', episode_length=args.steps,
                        obs_type='pixels_agent_pos', visualization_width=640, visualization_height=480,
                        init_states=True, num_steps_wait=10, control_mode='relative')
        report['stage'] = 'rollout'
        save()
        for index in range(args.episodes):
            seed = args.seed + index
            torch.manual_seed(seed)
            policy.reset()
            observation, _ = env.reset(seed=seed)
            native = env._env
            trace = []
            first_success = None
            video = folder / f'episode-{index}-seed-{seed}.mp4'
            # Use the exact training-oriented camera view, rendered at greater resolution.
            def render():
                return np.ascontiguousarray(native.env.sim.render(width=640, height=480, camera_name='agentview')[::-1, ::-1])
            frame = render()
            imageio.imwrite(video.with_suffix('.png'), frame)
            with imageio.get_writer(video, fps=20, codec='libx264') as writer:
                writer.append_data(frame)
                for step in range(args.steps):
                    batch = preprocess_observation(observation)
                    # Official evaluator uses vector environments. This native single
                    # environment needs the same leading batch dimension for robot state.
                    def batch_state(value):
                        if isinstance(value, dict):
                            return {key: batch_state(item) for key, item in value.items()}
                        return value.unsqueeze(0) if isinstance(value, torch.Tensor) else value
                    batch['observation.robot_state'] = batch_state(batch['observation.robot_state'])
                    batch['task'] = [task.language]
                    batch = pre(env_pre(batch))
                    with torch.inference_mode():
                        action = post(policy.select_action(batch))[0].cpu().numpy()
                    if action.shape != (7,) or not np.isfinite(action).all():
                        raise ValueError('Policy produced invalid native action')
                    observation, reward, terminated, truncated, info = env.step(action)
                    success = bool(native.check_success())
                    if success != bool(info['is_success']):
                        raise ValueError('Native and wrapped success flags disagree')
                    if success and first_success is None:
                        first_success = step+1
                    trace.append({'step': step+1, 'action': action.tolist(), 'reward': float(reward),
                                  'is_success': success, 'terminated': bool(terminated), 'truncated': bool(truncated)})
                    writer.append_data(render())
                    if (step+1) % 50 == 0:
                        print(f'episode={index} seed={seed} step={step+1} native_success={success}', flush=True)
            trace_path = video.with_suffix('.json')
            trace_path.write_text(json.dumps(trace, indent=2, allow_nan=False)+'\n')
            imageio.imwrite(folder / f'episode-{index}-final.png', render())
            run = {'episode': index, 'seed': seed, 'init_state_index': index, 'steps': len(trace),
                   'success': first_success is not None, 'first_success_step': first_success,
                   'final_success': trace[-1]['is_success'], 'best_reward': max(t['reward'] for t in trace),
                   'video': video.name, 'video_sha256': digest(video),
                   'trace': trace_path.name, 'trace_sha256': digest(trace_path)}
            report['runs'].append(run)
            report['successes'] = sum(r['success'] for r in report['runs'])
            report['episodes'] = len(report['runs'])
            report['success_rate'] = report['successes'] / report['episodes']
            save()
            print(json.dumps(run), flush=True)
        report['status'] = 'completed'
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        (folder / 'error.txt').write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        try:
            if env is not None:
                env.close()
        finally:
            save()
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
