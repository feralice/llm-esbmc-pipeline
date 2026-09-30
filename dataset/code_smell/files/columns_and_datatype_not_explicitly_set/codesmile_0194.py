# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/5/files/EvalID_84/dataset.py#L57-L61
# smelly line(s) in the original file: 61
# smelly line(s) in this file: 11
# ids: codesmile_0194
def load_dataset(ml_task_type=None, dataset_name=None):

    dataset_path = validate_dataset(ml_task_type, dataset_name)

    return pd.read_csv(dataset_path)
