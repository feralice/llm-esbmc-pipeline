# smell: Gradients Not Cleared Before Backward Propagation (R9)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_32/recom_amr.py#L163-L261
# smelly line(s) in the original file: 226
# smelly line(s) in this file: 70
# ids: codesmile_0365
def _fit_torch(self, train_set, train_features):
    import torch

    def _l2_loss(*tensors):
        l2_loss = 0
        for tensor in tensors:
            l2_loss += tensor.pow(2).sum()
        return l2_loss / 2

    def _inner(a, b):
        return (a * b).sum(dim=1)

    dtype = torch.float
    device = (
        torch.device("cuda:0")
        if (self.use_gpu and torch.cuda.is_available())
        else torch.device("cpu")
    )

    # set requireds_grad=True to get the adversarial gradient
    # if F is not put into the optimization list of parameters
    # it won't be updated
    F = torch.tensor(train_features, device=device, dtype=dtype, requires_grad=True)
    # Learned parameters
    Gu = torch.tensor(
        self.gamma_user, device=device, dtype=dtype, requires_grad=True
    )
    Gi = torch.tensor(
        self.gamma_item, device=device, dtype=dtype, requires_grad=True
    )
    E = torch.tensor(
        self.emb_matrix, device=device, dtype=dtype, requires_grad=True
    )

    optimizer = torch.optim.Adam([Gu, Gi, E], lr=self.learning_rate)

    for epoch in range(1, self.n_epochs + 1):
        sum_loss = 0.0
        count = 0
        progress_bar = tqdm(
            total=train_set.num_batches(self.batch_size),
            desc="Epoch {}/{}".format(epoch, self.n_epochs),
            disable=not self.verbose,
        )
        for batch_u, batch_i, batch_j in train_set.uij_iter(
            self.batch_size, shuffle=True
        ):
            gamma_u = Gu[batch_u]
            gamma_i = Gi[batch_i]
            gamma_j = Gi[batch_j]
            feat_i = F[batch_i]
            feat_j = F[batch_j]

            gamma_diff = gamma_i - gamma_j
            feat_diff = feat_i - feat_j

            Xuij = _inner(gamma_u, gamma_diff) + _inner(gamma_u, feat_diff.mm(E))

            log_likelihood = torch.nn.functional.logsigmoid(Xuij).sum()

            # adversarial part
            feat_i.retain_grad()
            feat_j.retain_grad()
            log_likelihood.backward(retain_graph=True)
            feat_i_delta = feat_i.grad
            feat_j_delta = feat_j.grad

            adv_feat_diff = feat_diff + (feat_i_delta - feat_j_delta)
            adv_Xuij = _inner(gamma_u, gamma_diff) + _inner(
                gamma_u, adv_feat_diff.mm(E)
            )

            adv_log_likelihood = torch.nn.functional.logsigmoid(adv_Xuij).sum()

            reg = (
                _l2_loss(gamma_u, gamma_i, gamma_j) * self.lambda_w
                + _l2_loss(E) * self.lambda_e
            )

            loss = -log_likelihood - self.lambda_adv * adv_log_likelihood + reg

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            sum_loss += loss.data.item()
            count += len(batch_u)
            if count % (self.batch_size * 10) == 0:
                progress_bar.set_postfix(loss=(sum_loss / count))
            progress_bar.update(1)
        progress_bar.close()

    print("Optimization finished!")

    self.gamma_user = Gu.data.cpu().numpy()
    self.gamma_item = Gi.data.cpu().numpy()
    self.emb_matrix = E.data.cpu().numpy()
    # pre-computed for faster evaluation
    self.theta_item = F.mm(E).data.cpu().numpy()
