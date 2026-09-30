# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_83/base_model.py#L67-L90
# smelly line(s) in the original file: 84
# smelly line(s) in this file: 24
# ids: codesmile_0338
def _fit_with_val(self, pyg_data, train_iters=1000, initialize=True, verbose=False, **kwargs):
    if initialize:
        self.initialize()

    # self.data = pyg_data[0].to(self.device)
    self.data = pyg_data.to(self.device)
    if verbose:
        print(f'=== training {self.name} model ===')
    optimizer = optim.Adam(self.parameters(), lr=self.lr, weight_decay=self.weight_decay)

    labels = self.data.y
    train_mask, val_mask = self.data.train_mask, self.data.val_mask

    x, edge_index = self.data.x, self.data.edge_index
    for i in range(train_iters):
        self.train()
        optimizer.zero_grad()
        output = self.forward(x, edge_index)
        loss_train = F.nll_loss(output[train_mask+val_mask], labels[train_mask+val_mask])
        loss_train.backward()
        optimizer.step()

        if verbose and i % 50 == 0:
            print('Epoch {}, training loss: {}'.format(i, loss_train.item()))
