# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_60/utils.py#L161-L169
# smelly line(s) in the original file: 162
# smelly line(s) in this file: 8
# ids: codesmile_0226
def get_nfold_split2(ifold, nfold=10):
    meta_train = pd.read_csv(os.path.join(settings.DATA_DIR, 'train_meta2.csv'))

    with open(os.path.join(settings.DATA_DIR, 'train_split.json'), 'r') as f:
        train_splits = json.load(f)
    train_index = train_splits[str(ifold)]['train_index']
    valid_index = train_splits[str(ifold)]['val_index']

    return meta_train.iloc[train_index], meta_train.iloc[valid_index]
