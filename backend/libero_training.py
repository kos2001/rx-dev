"""Official LeRobot training with pinned, verified single-task LIBERO demonstrations."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys

from .libero_runtime import DATASET_REVISION
from .learning_environments import ENVIRONMENTS
from .training import training_args
from .training_runner import check_device


def task_episode_ids(rows, task_index, count):
    """Reject mixed-task episodes and choose complete demonstrations deterministically."""
    tasks = {}
    for episode, task in rows:
        tasks.setdefault(int(episode), set()).add(int(task))
    selected = sorted(episode for episode, values in tasks.items() if values == {task_index})
    if len(selected) < count:
        raise ValueError(f'Selected LIBERO task has only {len(selected)} complete demonstrations')
    return selected[:count]


def select_demonstrations(config):
    import pyarrow.parquet as pq
    from huggingface_hub import snapshot_download
    root = Path(snapshot_download('lerobot/libero', repo_type='dataset', revision=DATASET_REVISION,
                                  allow_patterns=['meta/*', 'data/*']))
    tasks = pq.read_table(root/'meta/tasks.parquet').to_pandas()
    language = ENVIRONMENTS[config['environment']]['task'].replace('_', ' ')
    if language not in tasks.index:
        raise ValueError('Pinned dataset does not contain the selected simulator task')
    task_index = int(tasks.loc[language, 'task_index'])
    rows, receipts = [], []
    for path in sorted((root/'data').rglob('*.parquet')):
        table = pq.read_table(path, columns=['episode_index', 'task_index']).to_pydict()
        rows.extend(zip(table['episode_index'], table['task_index']))
        if any(int(task) == task_index for task in table['task_index']):
            receipts.append({'file': path.relative_to(root).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    episodes = task_episode_ids(rows, task_index, config['episodes'])
    info = json.loads((root/'meta/info.json').read_text())
    video_keys = [key for key, feature in info['features'].items() if feature['dtype'] == 'video']
    video_files = set()
    for path in (root/'meta/episodes').rglob('*.parquet'):
        for row in pq.read_table(path).to_pylist():
            if row['episode_index'] in episodes:
                for key in video_keys:
                    video_files.add(info['video_path'].format(video_key=key, chunk_index=row[f'videos/{key}/chunk_index'], file_index=row[f'videos/{key}/file_index']))
    if not video_files:
        raise ValueError('Selected demonstrations lack camera metadata')
    snapshot_download('lerobot/libero', repo_type='dataset', revision=DATASET_REVISION,
                      allow_patterns=sorted(video_files))
    return {'dataset': 'lerobot/libero', 'revision': DATASET_REVISION, 'task': language,
            'task_index': task_index, 'episode_indices': episodes, 'data_receipts': receipts,
            'images': 'canonical official dataset: two 256x256 images', 'state_dimension': 8, 'action_dimension': 7}, root


def train(config, output, checkpoint=None):
    import torch
    check_device(config['device'])
    torch.set_num_threads(4)
    selection, root = select_demonstrations(config)
    # Keep receipts outside trainer output: the official trainer requires a new output directory.
    (output.parent/'demonstrations.json').write_text(json.dumps(selection, indent=2))
    args = training_args(config, output, checkpoint)
    if config['mode'] != 'resume':
        args = [arg for arg in args if not arg.startswith('--dataset.episodes=')]
        args += [f"--dataset.episodes={json.dumps(selection['episode_indices'])}", f'--dataset.revision={DATASET_REVISION}', f'--dataset.root={root}']
    print('Verified single-task demonstrations:', selection['task'], 'episodes', selection['episode_indices'], 'revision', DATASET_REVISION, flush=True)
    sys.argv = ['lerobot-train', *args]
    runpy.run_module('lerobot.scripts.lerobot_train', run_name='__main__')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path)
    args = parser.parse_args()
    train(json.loads(args.config.read_text()), args.output, args.checkpoint)


if __name__ == '__main__':
    main()
