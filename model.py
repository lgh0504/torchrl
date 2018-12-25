import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from distribution import TanhNormal
# from distributions import Categorical, DiagGaussian
# from utils import init, init_normc_


class Flatten(nn.Module):
    def forward(self, x):
        return x.view(x.size(0), -1)

def init(module, weight_init, bias_init, gain=1):
    weight_init(module.weight.data, gain=gain)
    bias_init(module.bias.data)
    return module

LOG_SIG_MAX = 2
LOG_SIG_MIN = -20

class Policy(nn.Module):
    def __init__(self, obs_shape, action_space, hidden_shape ):
        
        super().__init__()

        init_ = lambda m: init(m,
            nn.init.orthogonal_,
            lambda x: nn.init.constant_(x, 0),
            np.sqrt(2))

        self.model = nn.Sequential(
            init_(nn.Linear( obs_shape, hidden_shape )),
            nn.Tanh(),
            init_(nn.Linear( hidden_shape, hidden_shape )),
            nn.Tanh(),
        )

        self.action = nn.Linear( hidden_shape, action_space )
        self.action.weight.data.uniform_(-1e-3, 1e-3)
        self.action.bias.data.uniform_(-1e-3, 1e-3)
        
        last_hidden_size = hidden_shape
        # if len(hidden_sizes) > 0:
        #     last_hidden_size = hidden_sizes[-1]
        self.last_fc_log_std = nn.Linear(last_hidden_size, action_space)
        self.last_fc_log_std.weight.data.uniform_(-1e-3, 1e-3)
        self.last_fc_log_std.bias.data.uniform_(-1e-3, 1e-3)
        
    def forward(self, x):
        
        hidden = self.model(x)
        
        mean = self.action( hidden )
        
        log_std = self.last_fc_log_std(hidden)
        log_std = torch.clamp(log_std, LOG_SIG_MIN, LOG_SIG_MAX)
        std = torch.exp(log_std)
        
        return mean, std
    
    def eval( self, x ):
        with torch.no_grad():
            hidden = self.model(x)
            mean = self.action(hidden)
        return torch.tanh(mean)
    
    def explore( self, x, return_pretanh_value = False ):
        
        mean, std = self.forward(x)

        dis = TanhNormal(mean, std)

        ent = dis.entropy().sum(1, keepdim=True) 
        
        if return_pretanh_value:
            action, z = dis.rsample( return_pretanh_value = True )
            return mean, std, action, z, ent

        else:
            action = dis.rsample( return_pretanh_value = False )
            return mean, std, action, ent
    
    def get_log_probs(self, mean, std, action, pre_tanh_value = None):
        
        dis = TanhNormal (mean, std )

        log_probs = dis.log_prob( action, pre_tanh_value ).sum(1,keepdim=True)

        return log_probs 
    

class QNet(nn.Module):
    def __init__(self, obs_shape, action_space, hidden_shape ):
        
        super().__init__()
        init_ = lambda m: init(m,
            nn.init.orthogonal_,
            lambda x: nn.init.constant_(x, 0),
            np.sqrt(2))

        self.fc1 = init_(nn.Linear( obs_shape  + action_space, hidden_shape ))
        self.fc2 = init_(nn.Linear( hidden_shape, hidden_shape ) )
        self.q_fun = init_( nn.Linear( hidden_shape, 1 ) )
    
    def forward(self, state, action):
        out = torch.cat( [state, action], 1 )
        out = F.relu(self.fc1(out))
        out = F.relu(self.fc2(out))
        out = self.q_fun(out)

        return out

class VNet(nn.Module):
    def __init__(self, obs_shape, hidden_shape ):
        
        super().__init__()

        init_ = lambda m: init(m,
            nn.init.orthogonal_,
            lambda x: nn.init.constant_(x, 0),
            np.sqrt(2))

        self.model = nn.Sequential(
            init_(nn.Linear( obs_shape, hidden_shape )),
            nn.ReLU(),
            init_(nn.Linear( hidden_shape, hidden_shape )),
            nn.ReLU(),
            init_(nn.Linear( hidden_shape, 1 )),
        )
        
    def forward(self, x):
        value = self.model(x)
        return value



# class Policy(nn.Module):
#     def __init__(self, obs_shape, action_space, base_kwargs=None):
#         super(Policy, self).__init__()
#         if base_kwargs is None:
#             base_kwargs = {}

#         if len(obs_shape) == 3:
#             self.base = CNNBase(obs_shape[0], **base_kwargs)
#         elif len(obs_shape) == 1:
#             self.base = MLPBase(obs_shape[0], **base_kwargs)
#         else:
#             raise NotImplementedError

#         if action_space.__class__.__name__ == "Discrete":
#             num_outputs = action_space.n
#             self.dist = Categorical(self.base.output_size, num_outputs)
#         elif action_space.__class__.__name__ == "Box":
#             num_outputs = action_space.shape[0]
#             self.dist = DiagGaussian(self.base.output_size, num_outputs)
#         else:
#             raise NotImplementedError

#     @property
#     def is_recurrent(self):
#         return self.base.is_recurrent

#     @property
#     def recurrent_hidden_state_size(self):
#         """Size of rnn_hx."""
#         return self.base.recurrent_hidden_state_size

#     def forward(self, inputs, rnn_hxs, masks):
#         raise NotImplementedError

#     def act(self, inputs, rnn_hxs, masks, deterministic=False):
#         value, actor_features, rnn_hxs = self.base(inputs, rnn_hxs, masks)
#         dist = self.dist(actor_features)

#         if deterministic:
#             action = dist.mode()
#         else:
#             action = dist.sample()

#         action_log_probs = dist.log_probs(action)
#         dist_entropy = dist.entropy().mean()

#         return value, action, action_log_probs, rnn_hxs

#     def get_value(self, inputs, rnn_hxs, masks):
#         value, _, _ = self.base(inputs, rnn_hxs, masks)
#         return value

#     def evaluate_actions(self, inputs, rnn_hxs, masks, action):
#         value, actor_features, rnn_hxs = self.base(inputs, rnn_hxs, masks)
#         dist = self.dist(actor_features)

#         action_log_probs = dist.log_probs(action)
#         dist_entropy = dist.entropy().mean()

#         return value, action_log_probs, dist_entropy, rnn_hxs


# class NNBase(nn.Module):

#     def __init__(self, recurrent, recurrent_input_size, hidden_size):
#         super(NNBase, self).__init__()

#         self._hidden_size = hidden_size
#         self._recurrent = recurrent

#         if recurrent:
#             self.gru = nn.GRU(recurrent_input_size, hidden_size)
#             for name, param in self.gru.named_parameters():
#                 if 'bias' in name:
#                     nn.init.constant_(param, 0)
#                 elif 'weight' in name:
#                     nn.init.orthogonal_(param)

#     @property
#     def is_recurrent(self):
#         return self._recurrent

#     @property
#     def recurrent_hidden_state_size(self):
#         if self._recurrent:
#             return self._hidden_size
#         return 1

#     @property
#     def output_size(self):
#         return self._hidden_size

#     def _forward_gru(self, x, hxs, masks):
#         if x.size(0) == hxs.size(0):
#             x, hxs = self.gru(x.unsqueeze(0), (hxs * masks).unsqueeze(0))
#             x = x.squeeze(0)
#             hxs = hxs.squeeze(0)
#         else:
#             # x is a (T, N, -1) tensor that has been flatten to (T * N, -1)
#             N = hxs.size(0)
#             T = int(x.size(0) / N)

#             # unflatten
#             x = x.view(T, N, x.size(1))

#             # Same deal with masks
#             masks = masks.view(T, N)

#             # Let's figure out which steps in the sequence have a zero for any agent
#             # We will always assume t=0 has a zero in it as that makes the logic cleaner
#             has_zeros = ((masks[1:] == 0.0) \
#                             .any(dim=-1)
#                             .nonzero()
#                             .squeeze()
#                             .cpu())


#             # +1 to correct the masks[1:]
#             if has_zeros.dim() == 0:
#                 # Deal with scalar
#                 has_zeros = [has_zeros.item() + 1]
#             else:
#                 has_zeros = (has_zeros + 1).numpy().tolist()

#             # add t=0 and t=T to the list
#             has_zeros = [0] + has_zeros + [T]


#             hxs = hxs.unsqueeze(0)
#             outputs = []
#             for i in range(len(has_zeros) - 1):
#                 # We can now process steps that don't have any zeros in masks together!
#                 # This is much faster
#                 start_idx = has_zeros[i]
#                 end_idx = has_zeros[i + 1]

#                 rnn_scores, hxs = self.gru(
#                     x[start_idx:end_idx],
#                     hxs * masks[start_idx].view(1, -1, 1)
#                 )

#                 outputs.append(rnn_scores)

#             # assert len(outputs) == T
#             # x is a (T, N, -1) tensor
#             x = torch.cat(outputs, dim=0)
#             # flatten
#             x = x.view(T * N, -1)
#             hxs = hxs.squeeze(0)

#         return x, hxs


# class CNNBase(NNBase):
#     def __init__(self, num_inputs, recurrent=False, hidden_size=512):
#         super(CNNBase, self).__init__(recurrent, hidden_size, hidden_size)

#         init_ = lambda m: init(m,
#             nn.init.orthogonal_,
#             lambda x: nn.init.constant_(x, 0),
#             nn.init.calculate_gain('relu'))

#         self.main = nn.Sequential(
#             init_(nn.Conv2d(num_inputs, 32, 8, stride=4)),
#             nn.ReLU(),
#             init_(nn.Conv2d(32, 64, 4, stride=2)),
#             nn.ReLU(),
#             init_(nn.Conv2d(64, 32, 3, stride=1)),
#             nn.ReLU(),
#             Flatten(),
#             init_(nn.Linear(32 * 7 * 7, hidden_size)),
#             nn.ReLU()
#         )

#         init_ = lambda m: init(m,
#             nn.init.orthogonal_,
#             lambda x: nn.init.constant_(x, 0))

#         self.critic_linear = init_(nn.Linear(hidden_size, 1))

#         self.train()

#     def forward(self, inputs, rnn_hxs, masks):
#         x = self.main(inputs / 255.0)

#         if self.is_recurrent:
#             x, rnn_hxs = self._forward_gru(x, rnn_hxs, masks)

#         return self.critic_linear(x), x, rnn_hxs


# class MLPBase(NNBase):
#     def __init__(self, num_inputs, recurrent=False, hidden_size=64):
#         super(MLPBase, self).__init__(recurrent, num_inputs, hidden_size)

#         if recurrent:
#             num_inputs = hidden_size

#         init_ = lambda m: init(m,
#             init_normc_,
#             lambda x: nn.init.constant_(x, 0))

#         self.actor = nn.Sequential(
#             init_(nn.Linear(num_inputs, hidden_size)),
#             nn.Tanh(),
#             init_(nn.Linear(hidden_size, hidden_size)),
#             nn.Tanh()
#         )

#         self.critic = nn.Sequential(
#             init_(nn.Linear(num_inputs, hidden_size)),
#             nn.Tanh(),
#             init_(nn.Linear(hidden_size, hidden_size)),
#             nn.Tanh()
#         )

#         self.critic_linear = init_(nn.Linear(hidden_size, 1))

#         self.train()

#     def forward(self, inputs, rnn_hxs, masks):
#         x = inputs

#         if self.is_recurrent:
#             x, rnn_hxs = self._forward_gru(x, rnn_hxs, masks)

#         hidden_critic = self.critic(x)
#         hidden_actor = self.actor(x)

#         return self.critic_linear(hidden_critic), hidden_actor, rnn_hxs
