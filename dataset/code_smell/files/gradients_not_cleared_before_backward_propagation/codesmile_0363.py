# smell: Gradients Not Cleared Before Backward Propagation (R9)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_25/CachedMultipleNegativesRankingLoss.py#L214-L241
# smelly line(s) in the original file: 234
# smelly line(s) in this file: 27
# ids: codesmile_0363
def calculate_loss_and_cache_gradients(self, reps: list[list[Tensor]]) -> Tensor:
    """Calculate the cross-entropy loss and cache the gradients wrt. the embeddings."""
    embeddings_a = torch.cat(reps[0])  # (bsz, hdim)
    embeddings_b = torch.cat([torch.cat(r) for r in reps[1:]])  # ((1 + nneg) * bsz, hdim)

    batch_size = len(embeddings_a)
    labels = torch.tensor(
        range(batch_size), dtype=torch.long, device=embeddings_a.device
    )  # (bsz, (1 + nneg) * bsz)  Example a[i] should match with b[i]
    losses: list[torch.Tensor] = []
    for b in tqdm.trange(
        0,
        batch_size,
        self.mini_batch_size,
        desc="Preparing caches",
        disable=not self.show_progress_bar,
    ):
        e = b + self.mini_batch_size
        scores: Tensor = self.similarity_fct(embeddings_a[b:e], embeddings_b) * self.scale
        loss_mbatch: torch.Tensor = self.cross_entropy_loss(scores, labels[b:e]) * len(scores) / batch_size
        loss_mbatch.backward()
        losses.append(loss_mbatch.detach())

    loss = sum(losses).requires_grad_()

    self.cache = [[r.grad for r in rs] for rs in reps]  # e.g. 3 * bsz/mbsz * (mbsz, hdim)

    return loss
