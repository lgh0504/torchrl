from .atari_wrapper import *
from .continuous_wrapper import *
from .base_wrapper import *

def wrap_deepmind(env, frame_stack=False, scale=False, clip_rewards=False):
    assert 'NoFrameskip' in env.spec.id
    env = EpisodicLifeEnv(env)
    env = NoopResetEnv(env, noop_max=30)
    env = MaxAndSkipEnv(env, skip=4)
    if 'FIRE' in env.unwrapped.get_action_meanings():
        env = FireResetEnv(env)
    env = WarpFrame(env)
    if scale:
        env = ScaledFloatFrame(env)
    if clip_rewards:
        env = ClipRewardEnv(env)
    if frame_stack:
        env = FrameStack(env, 4)
    return env


def wrap_continuous_env(env, obs_norm, reward_scale):
    env = RewardShift(env, reward_scale)
    if obs_norm:
        return NormObs(env)
    return env


def get_env(env_id, env_param):
    env = gym.make(env_id)
    if str(env.__class__.__name__).find('TimeLimit') >= 0:
        env = TimeLimitAugment(env)
    env = BaseWrapper(env)
    if "rew_norm" in env_param:
        env = NormRet(env, **env_param["rew_norm"])
        del env_param["rew_norm"]

    ob_space = env.observation_space
    if len(ob_space.shape) == 3:
        env = wrap_deepmind(env, **env_param)
    else:
        env = wrap_continuous_env(env, **env_param)


    # act_space = env.action_space
    # if isinstance(act_space, gym.spaces.Box):
    #     return NormAct(env)
    return env
