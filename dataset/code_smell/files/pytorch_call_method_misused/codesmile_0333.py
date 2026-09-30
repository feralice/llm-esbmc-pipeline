# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_67/base_model.py#L125-L130
# smelly line(s) in the original file: 127
# smelly line(s) in this file: 9
# ids: codesmile_0333
def training_step(self, batch, batch_idx):
    ori_text, cor_text, det_labels = batch
    outputs = self.forward(ori_text, cor_text, det_labels)
    loss = self.w * outputs[1] + (1 - self.w) * outputs[0]
    self.log('train_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True, batch_size=len(ori_text))
    return loss
