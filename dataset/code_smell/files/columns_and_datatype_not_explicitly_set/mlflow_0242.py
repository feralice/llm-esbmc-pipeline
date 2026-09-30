# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L216-L217
# smelly line(s) in the original file: 217
# smelly line(s) in this file: 8
# ids: mlflow_0242
def custom_load_file_as_dataframe(file_path, file_format):  # pylint: disable=unused-argument
    return pd.read_csv(file_path, sep="#", index_col=0)
