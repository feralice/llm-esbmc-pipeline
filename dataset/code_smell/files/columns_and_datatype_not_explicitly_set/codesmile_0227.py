# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_60/utils.py#L172-L176
# smelly line(s) in the original file: 173
# smelly line(s) in this file: 8
# ids: codesmile_0227
def get_test_meta():
    meta = pd.read_csv(settings.META_FILE, na_filter=False)
    test_meta = meta[meta['is_train'] == 0]
    print(len(test_meta.values))
    return test_meta
