"""Pinned simulator contracts shared by training, evaluation and agents."""
ENVIRONMENTS = {
    "pusht": {"name": "PushT", "type": "pusht", "task": "PushT-v0", "engine": "Pymunk",
              "dataset": "lerobot/pusht", "state_input": "state", "success_criterion": "is_success: coverage > 0.95"},
    "aloha": {"name": "ALOHA · Peg insertion", "type": "aloha", "task": "AlohaInsertion-v0", "engine": "MuJoCo",
              "dataset": "lerobot/aloha_sim_insertion_scripted", "state_input": "aloha_joint_object_state", "success_criterion": "is_success: native reward == 4"},
    "transfer": {"name": "ALOHA · Cube transfer", "type": "aloha", "task": "AlohaTransferCube-v0", "engine": "MuJoCo",
                 "dataset": "lerobot/aloha_sim_transfer_cube_scripted", "state_input": "aloha_joint_object_state", "success_criterion": "is_success: native reward == 4"},
    "libero_drawer": {"name": "LIBERO · 가운데 서랍 열기", "type": "libero", "task": "open_the_middle_drawer_of_the_cabinet", "engine": "MuJoCo",
                      "suite": "libero_goal", "task_id": 0, "dataset": "lerobot/libero", "state_input": "pixels_agent_pos", "success_criterion": "native LIBERO check_success()"},
    "libero_basket": {"name": "LIBERO · 수프 통조림 바구니 넣기", "type": "libero", "task": "pick_up_the_alphabet_soup_and_place_it_in_the_basket", "engine": "MuJoCo",
                      "suite": "libero_object", "task_id": 0, "dataset": "lerobot/libero", "state_input": "pixels_agent_pos", "success_criterion": "native LIBERO check_success()"},
}


def is_libero(config):
    return environment_of(config).startswith("libero_")


def environment_of(config):
    # Older persisted records did not store the environment.
    return config.get("environment") or next((key for key, value in ENVIRONMENTS.items()
                                              if value["dataset"] == config.get("dataset")), "pusht")


def evaluation_supported(config):
    return not config.get("dataset") or config["dataset"] == ENVIRONMENTS[environment_of(config)]["dataset"]
