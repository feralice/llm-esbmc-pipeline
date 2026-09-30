# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_65/sgc.py#L151-L169
# smelly line(s) in the original file: 162
# smelly line(s) in this file: 18
# ids: codesmile_0351
def test(self):
    """Evaluate SGC performance on test set.

    Parameters
    ----------
    idx_test :
        node testing indices
    """
    self.eval()
    test_mask = self.data.test_mask
    labels = self.data.y
    output = self.forward(self.data)
    # output = self.output
    loss_test = F.nll_loss(output[test_mask], labels[test_mask])
    acc_test = utils.accuracy(output[test_mask], labels[test_mask])
    print("Test set results:",
          "loss= {:.4f}".format(loss_test.item()),
          "accuracy= {:.4f}".format(acc_test.item()))
    return acc_test.item()
