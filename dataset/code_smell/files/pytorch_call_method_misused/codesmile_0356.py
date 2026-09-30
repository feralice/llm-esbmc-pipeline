# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_66/ac.py#L144-L166
# smelly line(s) in the original file: 150, 153, 160
# smelly line(s) in this file: 13, 16, 23
# ids: codesmile_0356, codesmile_0357, codesmile_0358
def select_action(self, state):
    '''
    only select action without the purpose of gradients flow, for interaction with env to
    generate samples
    '''
    if DETERMINISTIC:
        action = self.forward(state)

    if DISCRETE and not DETERMINISTIC:
        probs = self.forward(state)
        m = Categorical(probs)
        action = m.sample()

    if not DISCRETE and not DETERMINISTIC:
        self.action_range = 30.

        mean, log_std = self.forward(state)
        std = log_std.exp()
        normal = Normal(0, 1)
        z = normal.sample().to(device)
        action = self.action_range* torch.tanh(mean + std*z)

    return action.detach()
