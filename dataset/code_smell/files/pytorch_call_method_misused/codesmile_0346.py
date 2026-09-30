# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_90/sac_pendulum.py#L153-L163
# smelly line(s) in the original file: 155
# smelly line(s) in this file: 9
# ids: codesmile_0346
def get_action(self, state):
    state = torch.FloatTensor(state).unsqueeze(0).to(device)
    mean, log_std = self.forward(state)
    std = log_std.exp()

    normal = Normal(0, 1)
    z      = normal.sample(mean.shape).to(device)
    action = torch.tanh(mean + std*z)

    action  = action.cpu()#.detach().cpu().numpy()
    return action[0]
