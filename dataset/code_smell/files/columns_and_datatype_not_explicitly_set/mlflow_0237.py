# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L97-L98
# smelly line(s) in the original file: 98
# smelly line(s) in this file: 8
# ids: mlflow_0237
def custom_load_csv(file_path, file_format):  # pylint: disable=unused-argument
    return pd.read_csv(file_path, index_col=0)
