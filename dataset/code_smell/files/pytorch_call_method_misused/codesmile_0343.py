# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_64/scripted_seq2seq_generator.py#L105-L129
# smelly line(s) in the original file: 121
# smelly line(s) in this file: 23
# ids: codesmile_0343
def generate_hypo(self, tensors: Dict[str, torch.Tensor]):

    actual_src_tokens = tensors["src_tokens"].t()
    dict_feat: Optional[Tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = None

    if "dict_tokens" in tensors:
        dict_feat = (
            tensors["dict_tokens"],
            tensors["dict_weights"],
            tensors["dict_lengths"],
        )

    contextual_token_embedding: Optional[torch.Tensor] = None
    if "contextual_token_embedding" in tensors:
        contextual_token_embedding = tensors["contextual_token_embedding"]

    hypos_etc = self.forward(
        actual_src_tokens,
        dict_feat,
        contextual_token_embedding,
        tensors["src_lengths"],
    )
    predictions = [[pred for pred, _, _, _, _ in hypos_etc]]
    scores = [[score for _, score, _, _, _ in hypos_etc]]
    return (predictions, scores)
