# smell: NaN Equivalence Comparison Misused (R18)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_59/__init__.py#L294-L303
# smelly line(s) in the original file: 298
# smelly line(s) in this file: 11
# ids: codesmile_0146
def update(self, state, action, reward, next_state, done):
    '''Interface update method for body at agent.update()'''
    if hasattr(self.env.u_env, 'raw_reward'):  # use raw_reward if reward is preprocessed
        reward = self.env.u_env.raw_reward
    if self.ckpt_total_reward is np.nan:  # init
        self.ckpt_total_reward = reward
    else:  # reset on epi_start, else keep adding. generalized for vec env
        self.ckpt_total_reward = self.ckpt_total_reward * (1 - self.epi_start) + reward
    self.total_reward = done * self.ckpt_total_reward + (1 - done) * self.total_reward
    self.epi_start = done
