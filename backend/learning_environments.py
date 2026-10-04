"""Pinned simulator contracts shared by training, evaluation and agents."""
ENVIRONMENTS = {
    "pusht": {"name": "PushT", "type": "pusht", "task": "PushT-v0", "engine": "Pymunk",
              "dataset": "lerobot/pusht", "state_input": "state", "success_criterion": "is_success: coverage > 0.95"},
    "aloha": {"name": "ALOHA · Peg insertion", "type": "aloha", "task": "AlohaInsertion-v0", "engine": "MuJoCo",
              "dataset": "lerobot/aloha_sim_insertion_scripted", "state_input": "aloha_joint_object_state", "success_criterion": "is_success: native reward == 4"},
    "transfer": {"name": "ALOHA · Cube transfer", "type": "aloha", "task": "AlohaTransferCube-v0", "engine": "MuJoCo",
                 "dataset": "lerobot/aloha_sim_transfer_cube_scripted", "state_input": "aloha_joint_object_state", "success_criterion": "is_success: native reward == 4"},
}


def environment_of(config):
    # Older persisted records did not store the environment.
    return config.get("environment") or next((key for key, value in ENVIRONMENTS.items()
                                              if value["dataset"] == config.get("dataset")), "pusht")


def evaluation_supported(config):
    return not config.get("dataset") or config["dataset"] == ENVIRONMENTS[environment_of(config)]["dataset"]
