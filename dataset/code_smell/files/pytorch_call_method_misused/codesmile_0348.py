# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_68/mnist_ptl_mini.py#L99-L104
# smelly line(s) in the original file: 101
# smelly line(s) in this file: 9
# ids: codesmile_0348
def validation_step(self, val_batch, batch_idx):
    x, y = val_batch
    logits = self.forward(x)
    loss = F.nll_loss(logits, y)
    acc = self.accuracy(logits, y)
    return {"val_loss": loss, "val_accuracy": acc}
