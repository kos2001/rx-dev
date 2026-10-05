"""Guard the two published camera conventions against silent policy input mismatches."""
import unittest

from backend.libero_policies import POLICIES, policy_observation


class LiberoPolicyInputs(unittest.TestCase):
    def test_model_specific_camera_orientation_and_state_shape(self):
        import numpy as np
        import torch
        from lerobot.processor import LiberoProcessorStep, PolicyProcessorPipeline

        image = np.arange(60, dtype=np.uint8).reshape(4, 5, 3)
        observation = {'pixels': {'image': image, 'image2': image+64},
                       'robot_state': {'eef': {'pos': np.array([1., 2., 3.]),
                                               'quat': np.array([0., 0., 0., 1.])},
                                       'gripper': {'qpos': np.array([.04, .04])}}}
        processor = PolicyProcessorPipeline(steps=[LiberoProcessorStep()])
        expected = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float()/255
        drawer = policy_observation(observation, processor)
        basket = policy_observation(observation, processor, raw_camera_images=True)
        self.assertTrue(torch.equal(drawer['observation.images.image'], expected.flip(2, 3)))
        self.assertTrue(torch.equal(basket['observation.images.image'], expected))
        expected_wrist = torch.from_numpy(image+64).permute(2, 0, 1).unsqueeze(0).float()/255
        self.assertTrue(torch.equal(basket['observation.images.image2'], expected_wrist))
        for batch in [drawer, basket]:
            self.assertEqual(tuple(batch['observation.state'].shape), (1, 8))
            self.assertTrue(torch.allclose(batch['observation.state'], torch.tensor([[1., 2., 3., 0., 0., 0., .04, .04]])))

    def test_single_task_checkpoint_profiles_keep_distinct_contracts(self):
        self.assertEqual(POLICIES['drawer']['suite'], 'libero_goal')
        self.assertEqual(POLICIES['basket']['suite'], 'libero_object')
        self.assertEqual(POLICIES['basket']['image_size'], 128)
        self.assertTrue(POLICIES['basket']['raw_camera_images'])
        self.assertEqual(POLICIES['basket']['n_action_steps'], 1)
        self.assertEqual(POLICIES['basket']['temporal_ensemble_coeff'], .01)


if __name__ == '__main__':
    unittest.main()
