# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_81/dataset.py#L128-L142
# smelly line(s) in the original file: 138, 139, 140
# smelly line(s) in this file: 17, 18, 19
# ids: codesmile_0198, codesmile_0199, codesmile_0200
def get_idx_split(self, split_type = None):
    if split_type is None:
        split_type = self.meta_info['split']

    path = osp.join(self.root, 'split', split_type)

    # short-cut if split_dict.pt exists
    if os.path.isfile(os.path.join(path, 'split_dict.pt')):
        return torch.load(os.path.join(path, 'split_dict.pt'))

    train_idx = pd.read_csv(osp.join(path, 'train.csv.gz'), compression='gzip', header = None).values.T[0]
    valid_idx = pd.read_csv(osp.join(path, 'valid.csv.gz'), compression='gzip', header = None).values.T[0]
    test_idx = pd.read_csv(osp.join(path, 'test.csv.gz'), compression='gzip', header = None).values.T[0]

    return {'train': train_idx, 'valid': valid_idx, 'test': test_idx}
