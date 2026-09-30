# smell: NaN Equivalence Comparison Misused (R18)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_60/utils.py#L81-L86
# smelly line(s) in the original file: 85
# smelly line(s) in this file: 11
# ids: codesmile_0145
def get_salt_existence():
    train_mask = pd.read_csv(settings.LABEL_FILE)
    salt_exists_dict = {}
    for row in train_mask.values:
        salt_exists_dict[row[0]] = 0 if (row[1] is np.nan or len(row[1]) < 1) else 1
    return salt_exists_dict
