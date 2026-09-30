# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_65/sgc.py#L171-L180
# smelly line(s) in the original file: 180
# smelly line(s) in this file: 16
# ids: codesmile_0352
def predict(self):
    """
    Returns
    -------
    torch.FloatTensor
        output (log probabilities) of SGC
    """

    self.eval()
    return self.forward(self.data)
