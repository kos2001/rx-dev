"""Run a public, already-trained ACT policy in real MuJoCo; keep every outcome."""
import argparse
import json
from pathlib import Path
import time


def run(model_path, output, seeds, steps=400, full_rollout=False):
    import gymnasium as gym
    import gym_aloha  # noqa: F401
    import imageio.v2 as imageio
    import torch
    from lerobot.envs.utils import preprocess_observation
    from lerobot.policies.act.modeling_act import ACTPolicy
    from lerobot.policies.factory import make_pre_post_processors

    torch.set_num_threads(4)
    output.mkdir(parents=True, exist_ok=False)
    policy = ACTPolicy.from_pretrained(model_path).to('cpu').eval()
    pre, post = make_pre_post_processors(policy.config, pretrained_path=model_path,
                 preprocessor_overrides={'device_processor':{'device':'cpu'}})
    env = gym.make('gym_aloha/AlohaTransferCube-v0', obs_type='pixels_agent_pos', max_episode_steps=steps)
    started = time.monotonic()
    runs = []
    try:
        for seed in seeds:
            policy.reset()
            observation, _ = env.reset(seed=seed)
            rewards = []
            success = False
            first_success_step = None
            video = output / f'transfer-act-{seed}.mp4'
            trace = []
            with imageio.get_writer(video, fps=50) as writer:
                physics = env.unwrapped._env.physics
                frame = physics.render(height=480, width=640, camera_id='angle')
                imageio.imwrite(video.with_suffix('.png'), frame)
                writer.append_data(frame)
                for step in range(steps):
                    with torch.inference_mode():
                        action = post(policy.select_action(pre(preprocess_observation(observation))))
                    observation, reward, terminated, truncated, info = env.step(action[0].cpu().numpy())
                    writer.append_data(physics.render(height=480, width=640, camera_id='angle'))
                    rewards.append(float(reward))
                    measured_success = bool(info['is_success'])
                    if measured_success and first_success_step is None:
                        first_success_step = step + 1
                    success = first_success_step is not None
                    trace.append({'step':step+1,'reward':float(reward),'is_success':measured_success})
                    if truncated or terminated and not full_rollout:
                        break
            run = {'environment':'gym_aloha/AlohaTransferCube-v0', 'seed':seed, 'steps':len(rewards),
                   'success':success,'max_reward':max(rewards),'video':video.name,
                   'first_success_step':first_success_step,'final_success':measured_success,
                   'name':f'transfer-act-{seed}', 'controller':'public pretrained ACT; no local training'}
            runs.append(run)
            (output / f'trace-{seed}.json').write_text(json.dumps(trace,indent=2)+'\n')
            result = {'method':'pretrained ACT', 'model':'lerobot/act_aloha_sim_transfer_cube_human',
                      'model_path':str(model_path),'training_origin':'public pretrained 80000-step checkpoint',
                      'success_rule':'native gym-aloha is_success, reward == 4',
                      'continue_after_first_success':full_rollout,
                      'model_revision':'ba73b2766f1371cdc133ca4efb97eb090d744625',
                      'seeds':seeds,'runs':runs,'success_rate':sum(r['success'] for r in runs)/len(runs),
                      'wall_seconds':time.monotonic()-started,'camera':'angle','video_fps':50}
            (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(run),flush=True)
    finally:
        env.close()
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seeds',type=int,nargs='+',default=[42000,42001,42002])
    parser.add_argument('--full-rollout',action='store_true',help='Keep recording to 400 steps after native success; preserve first and final success separately')
    args=parser.parse_args()
    result=run(args.model,args.output,args.seeds,full_rollout=args.full_rollout)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
