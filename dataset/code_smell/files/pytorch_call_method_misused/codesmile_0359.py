# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_66/ac.py#L169-L201
# smelly line(s) in the original file: 175, 179, 190
# smelly line(s) in this file: 13, 17, 28
# ids: codesmile_0359, codesmile_0360, codesmile_0361
def evaluate_action(self, state):
    '''
    evaluate action within GPU graph, for gradients flowing through it
    '''
    state = torch.FloatTensor(state).unsqueeze(0).to(device) # state dim: (N, dim of state)
    if DETERMINISTIC:
        action = self.forward(state)
        return action.detach().cpu().numpy()

    elif DISCRETE and not DETERMINISTIC:  # actor-critic (discrete)
        probs = self.forward(state)
        m = Categorical(probs)
        action = m.sample().to(device)
        log_prob = m.log_prob(action)

        return action.detach().cpu().numpy(), log_prob.squeeze(0), m.entropy().mean()

    elif not DISCRETE and not DETERMINISTIC: # soft actor-critic (continuous)
        self.action_range = 30.
        self.epsilon = 1e-6

        mean, log_std = self.forward(state)
        std = log_std.exp()
        normal = Normal(0, 1)
        z = normal.sample().to(device)
        action0 = torch.tanh(mean + std*z.to(device)) # TanhNormal distribution as actions; reparameterization trick
        action = self.action_range * action0

        log_prob = Normal(mean, std).log_prob(mean+ std*z.to(device)) - torch.log(1. - action0.pow(2) + self.epsilon) -  np.log(self.action_range)            
        log_prob = log_prob.sum(dim=1, keepdim=True)
        # print('mean: ', mean, 'log_std: ', log_std)
        # return action.item(), log_prob, z, mean, log_std
        return action.detach().cpu().numpy().squeeze(0), log_prob.squeeze(0), Normal(mean, std).entropy().mean()
