# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/evaluate/test_evaluation.py#L238-L247
# smelly line(s) in the original file: 241
# smelly line(s) in this file: 10
# ids: mlflow_0176
def get_linear_regressor_model_uri():
    X, y = get_diabetes_dataset()
    reg = sklearn.linear_model.LinearRegression()
    reg.fit(X, y)

    with mlflow.start_run() as run:
        mlflow.sklearn.log_model(reg, "reg_model")
        linear_regressor_model_uri = get_artifact_uri(run.info.run_id, "reg_model")

    return linear_regressor_model_uri
