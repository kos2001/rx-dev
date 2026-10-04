"""Check physics isolation and Gymnasium terminal-info handling."""
import unittest

import numpy as np

from pusht_agent import Planner, PushtEnv, Settings, gym, make_env


class PhysicsChecks(unittest.TestCase):
    def test_v2_planning_is_reproducible_and_does_not_mutate_live_state(self):
        live = gym.make("gym_pusht/PushT-v0", obs_type="state")
        first = Planner(Settings(controller_version="v2", phase_steps=3), 12345)
        second = Planner(Settings(controller_version="v2", phase_steps=3), 12345)
        try:
            state, info = live.reset(seed=300)
            before = live.unwrapped.get_obs().copy()
            action = first.action(state, info)
            np.testing.assert_array_equal(action, second.action(state, info))
            np.testing.assert_array_equal(live.unwrapped.get_obs(), before)
        finally:
            first.close()
            second.close()
            live.close()

    def test_prediction_restores_pose_and_preserves_live_environment(self):
        live = gym.make("gym_pusht/PushT-v0", obs_type="state")
        planner = Planner(Settings(), 123)
        try:
            state, info = live.reset(seed=42)
            before = live.unwrapped.get_obs().copy()
            planner.restore(state, info)
            np.testing.assert_allclose(planner.model.get_obs(), state, atol=1e-9)
            action = np.array([200, 300], dtype=np.float32)
            predicted, reward, _, _, _ = planner.model.step(action)
            np.testing.assert_array_equal(live.unwrapped.get_obs(), before)
            observed, real_reward, _, _, _ = live.step(action)
            np.testing.assert_allclose(predicted, observed, atol=1e-7)
            self.assertAlmostEqual(reward, real_reward, places=7)
        finally:
            planner.close()
            live.close()

    def test_success_info_survives_vector_autoreset(self):
        env = make_env(PushtEnv(obs_type="state"))["pusht"][0]
        try:
            state = [50, 50, 256, 256, np.pi / 4]
            # reset_to_state rotates around the CoM; put the measured origin back.
            env.reset(seed=42, options={"reset_to_state": state})
            raw = env.envs[0].unwrapped
            raw.block.position = [256, 256]
            raw.space.reindex_shapes_for_body(raw.block)
            _, reward, terminated, _, info = env.step(np.array([[50, 50]], dtype=np.float32))
            self.assertTrue(terminated[0])
            self.assertAlmostEqual(float(reward[0]), 1.0)
            self.assertTrue(info["final_info"]["is_success"][0])
            np.testing.assert_allclose(info["final_info"]["block_pose"][0][:2], [256, 256], atol=1e-7)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
