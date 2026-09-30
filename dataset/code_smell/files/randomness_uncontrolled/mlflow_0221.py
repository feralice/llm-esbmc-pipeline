# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/gluon/test_gluon_autolog.py#L125-L132
# smelly line(s) in the original file: 132
# smelly line(s) in this file: 14
# ids: mlflow_0221
def test_gluon_autolog_model_can_load_from_artifact(gluon_random_data_run):
    client = MlflowClient()
    artifacts = client.list_artifacts(gluon_random_data_run.info.run_id)
    artifacts = [x.path for x in artifacts]
    assert "model" in artifacts
    ctx = mx.cpu()
    model = mlflow.gluon.load_model("runs:/" + gluon_random_data_run.info.run_id + "/model", ctx)
    model(array_module.array(np.random.rand(1000, 1, 32)))
