# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/models/test_signature.py#L179-L192
# smelly line(s) in the original file: 183
# smelly line(s) in this file: 11
# ids: mlflow_0313
def test_set_signature_overwrite():
    artifact_path = "regr-model"
    with mlflow.start_run() as run:
        mlflow.sklearn.log_model(
            sk_model=RandomForestRegressor(),
            artifact_path=artifact_path,
            signature=infer_signature(np.array([1])),
        )
    new_signature = infer_signature(np.array([1]), np.array([1]))
    run_id = run.info.run_id
    model_uri = f"runs:/{run_id}/{artifact_path}"
    set_signature(model_uri, new_signature)
    model_info = get_model_info(model_uri)
    assert model_info.signature == new_signature
