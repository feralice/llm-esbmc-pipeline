# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/resources/mlflow-test-plugin/mlflow_test_plugin/dummy_evaluator.py#L24-L26
# smelly line(s) in the original file: 25
# smelly line(s) in this file: 8
# ids: mlflow_0088
def _load_content_from_file(self, local_artifact_path):
    pdf = pd.read_csv(local_artifact_path)
    return pdf.to_numpy()
