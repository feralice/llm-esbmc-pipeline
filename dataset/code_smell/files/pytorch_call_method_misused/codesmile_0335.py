# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_67/base_model.py#L179-L189
# smelly line(s) in the original file: 183
# smelly line(s) in this file: 11
# ids: codesmile_0335
def predict(self, texts):
    inputs = self.tokenizer(texts, padding=True, return_tensors='pt')
    inputs.to(self.cfg.MODEL.DEVICE)
    with torch.no_grad():
        outputs = self.forward(texts)
        y_hat = torch.argmax(outputs[1], dim=-1)
        expand_text_lens = torch.sum(inputs['attention_mask'], dim=-1) - 1
    rst = []
    for t_len, _y_hat in zip(expand_text_lens, y_hat):
        rst.append(self.tokenizer.decode(_y_hat[1:t_len]).replace(' ', ''))
    return rst
