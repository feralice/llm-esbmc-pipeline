# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/shap/test_log.py#L141-L160
# smelly line(s) in the original file: 148
# smelly line(s) in this file: 14
# ids: mlflow_0266
def test_log_explanation_doesnt_create_autologged_run():
    try:
        mlflow.sklearn.autolog(disable=False, exclusive=False)
        X, y = sklearn.datasets.load_diabetes(return_X_y=True, as_frame=True)
        X = X.iloc[:50, :4]
        y = y.iloc[:50]
        model = sklearn.linear_model.LinearRegression()
        model.fit(X, y)

        with mlflow.start_run() as run:
            mlflow.shap.log_explanation(model.predict, X)

        run_data = MlflowClient().get_run(run.info.run_id).data
        metrics, params, tags = run_data.metrics, run_data.params, run_data.tags
        assert not metrics
        assert not params
        assert all("mlflow." in key for key in tags)
        assert "mlflow.autologging" not in tags
    finally:
        mlflow.sklearn.autolog(disable=True)
