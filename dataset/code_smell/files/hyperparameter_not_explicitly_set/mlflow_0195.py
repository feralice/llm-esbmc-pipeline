# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/evaluate/test_evaluation.py#L1215-L1233
# smelly line(s) in the original file: 1219
# smelly line(s) in this file: 11
# ids: mlflow_0195
def test_evaluate_stdin_scoring_server():
    X, y = sklearn.datasets.load_iris(return_X_y=True)
    X = X[::5]
    y = y[::5]
    model = sklearn.linear_model.LogisticRegression()
    model.fit(X, y)

    with mlflow.start_run():
        model_info = mlflow.sklearn.log_model(model, "model")

    with mock.patch("mlflow.pyfunc.check_port_connectivity", return_value=False):
        mlflow.evaluate(
            model_info.model_uri,
            X,
            targets=y,
            model_type="classifier",
            evaluators=["default"],
            env_manager="virtualenv",
        )
