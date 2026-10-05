"""Bounded native LIBERO portability probe; no learned policy or success claim."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import sys
import time
import traceback

ASSET_REVISION = '0b3ea86be5fe169d0fd036ae63d1070ec09e90f6'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='outputs/platform-probes/libero-macos')
    parser.add_argument('--suite', choices=['libero_spatial', 'libero_object', 'libero_goal', 'libero_10'], default='libero_spatial')
    parser.add_argument('--task', type=int, default=0)
    parser.add_argument('--steps', type=int, default=60)
    parser.add_argument('--seed', type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.steps <= 200 or args.task < 0:
        parser.error('steps must be 1..200 and task must be nonnegative')
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    os.environ['LIBERO_CONFIG_PATH'] = str(folder / 'config')
    os.environ.setdefault('HF_HOME', str(folder.parent / 'hf-cache'))
    os.environ.setdefault('MPLCONFIGDIR', str(folder / 'matplotlib'))
    os.environ.setdefault('NUMBA_CACHE_DIR', str(folder / 'numba'))
    os.environ.setdefault('MUJOCO_GL', 'cgl' if sys.platform == 'darwin' else 'egl')
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    report = {'status': 'started', 'purpose': 'portability_smoke', 'learned_policy': False,
              'host': platform.platform(), 'architecture': platform.machine(),
              'config': vars(args), 'asset_revision': ASSET_REVISION,
              'packages': {name: importlib.metadata.version(name) for name in ['hf-libero', 'robosuite', 'mujoco', 'numpy', 'torch']}}
    env = None
    started = time.monotonic()
    try:
        import numpy as np
        import yaml
        import imageio.v2 as imageio
        # Avoid upstream interactive configuration and user-home writes.
        spec = __import__('importlib.util', fromlist=['find_spec']).find_spec('libero')
        root = Path(next(iter(spec.submodule_search_locations))) / 'libero'
        config_dir = folder / 'config'
        config_dir.mkdir(exist_ok=True)
        assets = folder.parent / 'libero-assets'
        config = {'benchmark_root': str(root), 'bddl_files': str(root / 'bddl_files'),
                  'init_states': str(root / 'init_files'), 'datasets': str(folder / 'datasets'), 'assets': str(assets)}
        (config_dir / 'config.yaml').write_text(yaml.safe_dump(config))
        from libero.libero import benchmark, get_libero_path
        from libero.libero.envs import OffScreenRenderEnv
        report['stage'] = 'imports_completed'
        from huggingface_hub import snapshot_download
        print('Downloading pinned simulator assets', flush=True)
        snapshot_download('lerobot/libero-assets', repo_type='dataset', revision=ASSET_REVISION,
                          local_dir=str(assets), max_workers=8)
        import libero.libero as libero_module
        libero_module._assets_path_cache = str(assets)
        suite = benchmark.get_benchmark_dict()[args.suite]()
        if args.task >= suite.n_tasks:
            raise ValueError('task index outside selected suite')
        task = suite.get_task(args.task)
        report['task_name'] = task.name
        report['task_language'] = task.language
        bddl = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
        report['bddl_sha256'] = hashlib.sha256(bddl.read_bytes()).hexdigest()
        report['stage'] = 'environment_creation'
        print('Creating task:', task.name, flush=True)
        env = OffScreenRenderEnv(bddl_file_name=str(bddl), camera_heights=256, camera_widths=256)
        env.seed(args.seed)
        obs = env.reset()
        report['stage'] = 'rollout'
        traces = []
        # Bounded zero-end-effector-motion control, open gripper; validates execution only.
        action = np.array([0., 0., 0., 0., 0., 0., -1.])
        video_path = folder / 'rollout.mp4'
        with imageio.get_writer(video_path, fps=20, codec='libx264', macro_block_size=16) as writer:
            frame = np.ascontiguousarray(obs['agentview_image'][::-1])
            imageio.imwrite(folder / 'poster.png', frame)
            writer.append_data(frame)
            for step in range(args.steps):
                obs, reward, done, info = env.step(action)
                success = bool(env.check_success())
                traces.append({'step': step+1, 'reward': float(reward), 'success': success, 'done': bool(done)})
                writer.append_data(np.ascontiguousarray(obs['agentview_image'][::-1]))
        (folder / 'trace.json').write_text(json.dumps(traces, indent=2))
        report.update(status='completed', stage='recorded', steps=len(traces), frames=len(traces)+1,
                      native_success=any(t['success'] for t in traces),
                      observation_keys=list(obs), video=str(video_path),
                      video_sha256=hashlib.sha256(video_path.read_bytes()).hexdigest())
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        (folder / 'error.txt').write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        if env is not None:
            env.close()
        report['seconds'] = time.monotonic()-started
        (folder / 'result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2), flush=True)
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
