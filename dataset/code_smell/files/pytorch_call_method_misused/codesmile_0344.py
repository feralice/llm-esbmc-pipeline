# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_61/ppo_continuous_multiprocess.py#L150-L157
# smelly line(s) in the original file: 152
# smelly line(s) in this file: 9
# ids: codesmile_0344
def get_action(self, state, deterministic=False):
    state = torch.FloatTensor(state).unsqueeze(0).to(device)
    mean, log_std = self.forward(state)
    std = log_std.exp()
    normal = Normal(mean, std)
    action = normal.sample() 
    action = torch.clamp(action, -self.action_range, self.action_range)
    return action.squeeze(0)
