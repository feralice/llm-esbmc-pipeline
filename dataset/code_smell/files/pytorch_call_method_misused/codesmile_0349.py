# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_65/sgc.py#L108-L149
# smelly line(s) in the original file: 124, 134
# smelly line(s) in this file: 23, 33
# ids: codesmile_0349, codesmile_0350
def train_with_early_stopping(self, train_iters, patience, verbose):
    """early stopping based on the validation loss
    """
    if verbose:
        print('=== training SGC model ===')
    optimizer = optim.Adam(self.parameters(), lr=self.lr, weight_decay=self.weight_decay)

    labels = self.data.y
    train_mask, val_mask = self.data.train_mask, self.data.val_mask

    early_stopping = patience
    best_loss_val = 100

    for i in range(train_iters):
        self.train()
        optimizer.zero_grad()
        output = self.forward(self.data)

        loss_train = F.nll_loss(output[train_mask], labels[train_mask])
        loss_train.backward()
        optimizer.step()

        if verbose and i % 10 == 0:
            print('Epoch {}, training loss: {}'.format(i, loss_train.item()))

        self.eval()
        output = self.forward(self.data)
        loss_val = F.nll_loss(output[val_mask], labels[val_mask])

        if best_loss_val > loss_val:
            best_loss_val = loss_val
            self.output = output
            weights = deepcopy(self.state_dict())
            patience = early_stopping
        else:
            patience -= 1
        if i > early_stopping and patience <= 0:
            break

    if verbose:
         print('=== early stopping at {0}, loss_val = {1} ==='.format(i, best_loss_val) )
    self.load_state_dict(weights)
