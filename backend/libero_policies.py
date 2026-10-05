"""Pinned public single-task policy contracts; do not substitute tasks or image conventions."""
POLICIES = {
    'drawer': {
        'model': 'AmberHyunKIM/act_libero_goal_task0',
        'revision': '4db937e8de09123dd9b5707ab7704710000b5f25',
        'folder': 'act-libero-goal-task0', 'suite': 'libero_goal', 'task_id': 0,
        'task_name': 'open_the_middle_drawer_of_the_cabinet',
        'image_size': 256, 'raw_camera_images': False,
        'n_action_steps': 10, 'temporal_ensemble_coeff': None, 'default_steps': 300,
    },
    'basket': {
        'model': 'rishi264/act-libero-alphabet-soup',
        'revision': '4008ed10261d06404d04c04490dc572da2430b7a',
        'folder': 'act-libero-alphabet-soup', 'suite': 'libero_object', 'task_id': 0,
        'task_name': 'pick_up_the_alphabet_soup_and_place_it_in_the_basket',
        'image_size': 128, 'raw_camera_images': True,
        'n_action_steps': 1, 'temporal_ensemble_coeff': 0.01, 'default_steps': 400,
    },
}


def policy_observation(observation, env_processor, *, raw_camera_images=False):
    """Match the model's camera convention while using official LIBERO robot state processing."""
    import torch
    from lerobot.envs.utils import preprocess_observation

    batch = preprocess_observation(observation)

    def batch_state(value):
        if isinstance(value, dict):
            return {key: batch_state(item) for key, item in value.items()}
        return value.unsqueeze(0) if isinstance(value, torch.Tensor) else value

    batch['observation.robot_state'] = batch_state(batch['observation.robot_state'])
    images = {key: value for key, value in batch.items() if key.startswith('observation.images.')}
    batch = env_processor(batch)
    if raw_camera_images:
        # This checkpoint was trained on unflipped native camera frames. The
        # default LIBERO processor rotates both axes for the canonical dataset.
        batch.update(images)
    return batch
