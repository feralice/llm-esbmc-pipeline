# smell: Gradients Not Cleared Before Backward Propagation (R9)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_63/linr_layer.py#L207-L208
# smelly line(s) in the original file: 208
# smelly line(s) in this file: 8
# ids: codesmile_0374
def backward(self):
    self.z.backward(self.dz / self.dz.share.shape[0])
