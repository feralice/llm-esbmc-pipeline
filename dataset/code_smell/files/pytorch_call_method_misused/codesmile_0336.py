# smell: PyTorch Call Method Misused (R8)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_83/base_model.py#L23-L64
# smelly line(s) in the original file: 38, 48
# smelly line(s) in this file: 22, 32
# ids: codesmile_0336, codesmile_0337
def finetune(self, edge_index, edge_weight, feat=None, train_iters=10, verbose=True):
    if verbose:
        print(f'=== finetuning {self.name} model ===')
    optimizer = optim.Adam(self.parameters(), lr=self.lr, weight_decay=self.weight_decay)
    labels = self.data.y
    if feat is None:
        x = self.data.x
    else:
        x = feat
    train_mask, val_mask = self.data.train_mask, self.data.val_mask
    best_loss_val = 100
    best_acc_val = 0
    for i in range(train_iters):
        self.train()
        optimizer.zero_grad()
        output = self.forward(x, edge_index, edge_weight)
        loss_train = F.nll_loss(output[train_mask], labels[train_mask])
        loss_train.backward()
        optimizer.step()

        if verbose and i % 50 == 0:
            print('Epoch {}, training loss: {}'.format(i, loss_train.item()))

        self.eval()
        with torch.no_grad():
            output = self.forward(x, edge_index)
        loss_val = F.nll_loss(output[val_mask], labels[val_mask])
        acc_val = utils.accuracy(output[val_mask], labels[val_mask])

        # if best_loss_val > loss_val:
        #     best_loss_val = loss_val
        #     best_output = output
        #     weights = deepcopy(self.state_dict())

        if best_acc_val < acc_val:
            best_acc_val = acc_val
            best_output = output
            weights = deepcopy(self.state_dict())

    print('best_acc_val:', best_acc_val.item())
    self.load_state_dict(weights)
    return best_output
