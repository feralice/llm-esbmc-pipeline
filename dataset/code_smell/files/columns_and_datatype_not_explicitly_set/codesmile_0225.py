# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_60/utils.py#L148-L159
# smelly line(s) in the original file: 152
# smelly line(s) in this file: 11
# ids: codesmile_0225
def get_nfold_split(ifold, nfold=10, meta_version=1):
    if meta_version == 2:
        return get_nfold_split2(ifold, nfold)

    meta = pd.read_csv(settings.META_FILE, na_filter=False)
    meta_train = meta[meta['is_train'] == 1]

    kf = KFold(n_splits=nfold)
    for i, (train_index, valid_index) in enumerate(kf.split(meta_train[settings.ID_COLUMN].values.reshape(-1))):
        if i == ifold:
            break
    return meta_train.iloc[train_index], meta_train.iloc[valid_index]
