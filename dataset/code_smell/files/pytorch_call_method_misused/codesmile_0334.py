# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_67/base_model.py#L132-L154
# smelly line(s) in the original file: 134
# smelly line(s) in this file: 9
# ids: codesmile_0334
def validation_step(self, batch, batch_idx):
    ori_text, cor_text, det_labels = batch
    outputs = self.forward(ori_text, cor_text, det_labels)
    loss = self.w * outputs[1] + (1 - self.w) * outputs[0]
    det_y_hat = (outputs[2] > 0.5).long()
    cor_y_hat = torch.argmax((outputs[3]), dim=-1)
    encoded_x = self.tokenizer(cor_text, padding=True, return_tensors='pt')
    encoded_x.to(self._device)
    cor_y = encoded_x['input_ids']
    cor_y_hat *= encoded_x['attention_mask']

    results = []
    det_acc_labels = []
    cor_acc_labels = []
    for src, tgt, predict, det_predict, det_label in zip(ori_text, cor_y, cor_y_hat, det_y_hat, det_labels):
        _src = self.tokenizer(src, add_special_tokens=False)['input_ids']
        _tgt = tgt[1:len(_src) + 1].cpu().numpy().tolist()
        _predict = predict[1:len(_src) + 1].cpu().numpy().tolist()
        cor_acc_labels.append(1 if operator.eq(_tgt, _predict) else 0)
        det_acc_labels.append(det_predict[1:len(_src) + 1].equal(det_label[1:len(_src) + 1]))
        results.append((_src, _tgt, _predict,))

    return loss.cpu().item(), det_acc_labels, cor_acc_labels, results
