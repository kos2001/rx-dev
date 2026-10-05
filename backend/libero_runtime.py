"""Isolated LIBERO worker setup and fixed task/initial-state contracts."""
import os
from pathlib import Path
import sys

from .learning_environments import ENVIRONMENTS
from .libero_probe import ASSET_REVISION

ROOT = Path(__file__).resolve().parents[1]
DATASET_REVISION = 'a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4'


def worker_python():
    configured = os.environ.get('RX_LIBERO_PYTHON')
    path = Path(configured or ('/private/tmp/rx-dev-libero-macos-venv/bin/python' if sys.platform == 'darwin' else sys.executable))
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError('LIBERO worker unavailable. Run sh setup_libero_learning.sh first, or set RX_LIBERO_PYTHON.')
    return str(path)


def initial_state_index(seed, count):
    # Benchmark state selection must depend on the paired seed, not reset order.
    return seed % count


def prepare_runtime():
    import importlib.util
    import yaml
    from huggingface_hub import snapshot_download
    root = Path(next(iter(importlib.util.find_spec('libero').submodule_search_locations))) / 'libero'
    folder = Path(os.environ['LIBERO_CONFIG_PATH'])
    folder.mkdir(parents=True, exist_ok=True)
    assets = ROOT / 'outputs' / 'platform-probes' / 'libero-assets'
    snapshot_download('lerobot/libero-assets', repo_type='dataset', revision=ASSET_REVISION, local_dir=str(assets))
    config = {'benchmark_root': str(root), 'bddl_files': str(root/'bddl_files'),
              'init_states': str(root/'init_files'), 'datasets': str(ROOT/'outputs'/'libero-datasets'), 'assets': str(assets)}
    (folder/'config.yaml').write_text(yaml.safe_dump(config))
    import libero.libero as module
    module._assets_path_cache = str(assets)
    return root


def make_env(config, height, width):
    prepare_runtime()
    from libero.libero import benchmark
    from lerobot.envs.libero import LiberoEnv
    spec = ENVIRONMENTS[config['environment']]
    suite = benchmark.get_benchmark_dict()[spec['suite']]()
    task = suite.get_task(spec['task_id'])
    if task.name != spec['task']:
        raise ValueError('LIBERO task identity mismatch')
    return LiberoEnv(suite, spec['task_id'], spec['suite'], episode_length=config['step_limit'],
                     observation_height=height, observation_width=width, obs_type='pixels_agent_pos',
                     init_states=True, num_steps_wait=10, control_mode='relative')
