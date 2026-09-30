# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_83/base_model.py#L101-L160
# smelly line(s) in the original file: 121, 131
# smelly line(s) in this file: 27, 37
# ids: codesmile_0339, codesmile_0340
def train_with_early_stopping(self, train_iters, patience, verbose):
    """early stopping based on the validation loss
    """
    if verbose:
        print(f'=== training {self.name} model ===')
    optimizer = optim.Adam(self.parameters(), lr=self.lr, weight_decay=self.weight_decay)

    labels = self.data.y
    train_mask, val_mask = self.data.train_mask, self.data.val_mask

    early_stopping = patience
    best_loss_val = 100
    best_acc_val = 0
    best_epoch = 0

    x, edge_index = self.data.x, self.data.edge_index
    for i in range(train_iters):
        self.train()
        optimizer.zero_grad()

        output = self.forward(x, edge_index)

        loss_train = F.nll_loss(output[train_mask], labels[train_mask])
        loss_train.backward()
        optimizer.step()

        if verbose and i % 50 == 0:
            print('Epoch {}, training loss: {}'.format(i, loss_train.item()))

        self.eval()
        output = self.forward(x, edge_index)
        loss_val = F.nll_loss(output[val_mask], labels[val_mask])
        acc_val = utils.accuracy(output[val_mask], labels[val_mask])
        # print(acc)

        # if best_loss_val > loss_val:
        #     best_loss_val = loss_val
        #     self.output = output
        #     weights = deepcopy(self.state_dict())
        #     patience = early_stopping
        #     best_epoch = i
        # else:
        #     patience -= 1

        if best_acc_val < acc_val:
            best_acc_val = acc_val
            self.output = output
            weights = deepcopy(self.state_dict())
            patience = early_stopping
            best_epoch = i
        else:
            patience -= 1

        if i > early_stopping and patience <= 0:
            break

    if verbose:
         # print('=== early stopping at {0}, loss_val = {1} ==='.format(best_epoch, best_loss_val) )
         print('=== early stopping at {0}, acc_val = {1} ==='.format(best_epoch, best_acc_val) )
    self.load_state_dict(weights)
