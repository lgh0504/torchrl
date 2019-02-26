import time
import numpy as np
import copy

import torch.optim as optim
import pytorch_util as ptu
import torch
from torch import nn as nn

from algo.rl_algo import RLAlgo
import math

class DQN(RLAlgo):
    def __init__(self, 
        qf, pf, pretrain_pf,
        qlr,
        optimizer_class=optim.Adam,
        optimizer_info = {},
        **kwargs
    ):
        super(DQN, self).__init__(**kwargs)
        
        self.pf = pf
        self.pretrain_pf = pretrain_pf
        self.qf = qf
        self.target_qf = copy.deepcopy(qf)
        self.qlr = qlr
        self.qf_optimizer = optimizer_class(
            self.qf.parameters(),
            lr=self.qlr,
            **optimizer_info
        )
        
        self.to(self.device)
        self.qf_criterion = nn.MSELoss()
        
    def get_actions(self, policy, ob):
        return policy.explore( torch.Tensor( ob ).to(self.device).unsqueeze(0) )["action"]

    def get_pretrain_actions(self, policy, ob):
        return policy.explore( torch.Tensor( ob ).to(self.device).unsqueeze(0) )["action"]

    def update(self, batch):
        self.training_update_num += 1
        rewards = batch['rewards']
        terminals = batch['terminals']
        obs = batch['observations']
        actions = batch['actions']
        next_obs = batch['next_observations']

        rewards = torch.Tensor(rewards).to( self.device )
        terminals = torch.Tensor(terminals).to( self.device )
        obs = torch.Tensor(obs).to( self.device )
        actions = torch.Tensor(actions).to( self.device )
        next_obs = torch.Tensor(next_obs).to( self.device )

        q_pred = self.qf(obs)
        q_s_a = q_pred.gather( 1, actions.unsqueeze(1).long() ) 
        next_q_pred = self.target_qf( next_obs )

        target_q_s_a = rewards + self.discount * ( 1 - terminals) * next_q_pred.max(1, keepdim=True)[0]
        # print(target_q_s_a.shape)
        # print(rewards.shape)
        # print(terminals.shape)
        # print(next_q_pred.max(1)[0].shape)
        qf_loss = self.qf_criterion( q_s_a, target_q_s_a.detach() )

        self.qf_optimizer.zero_grad()
        qf_loss.backward()
        self.qf_optimizer.step()
        
        self._update_target_networks()

        # Information For Logger
        info = {}
        info['Reward_Mean'] = rewards.mean().item()
        info['Traning/qf_loss'] = qf_loss.item()
        info['epsilon']= self.pf.epsilon
        info['q_s_a'] = q_s_a.mean().item()
        return info
        

    @property
    def networks(self):
        return [
            self.qf,
            self.target_qf
        ]
    
    @property
    def target_networks(self):
        return [
            ( self.qf, self.target_qf )
        ]