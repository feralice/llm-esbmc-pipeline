# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/shap/test_log.py#L116-L138
# smelly line(s) in the original file: 128
# smelly line(s) in this file: 19
# ids: mlflow_0265
def test_sklearn_log_explainer_pyfunc():
    """
    Tests mlflow.shap log_explainer with mlflow
    serialization of the underlying model using pyfunc flavor
    """

    with mlflow.start_run() as run:
        run_id = run.info.run_id

        X, y = get_housing_data()

        model = sklearn.ensemble.RandomForestRegressor(n_estimators=100)
        model.fit(X, y)

        explainer_original = shap.Explainer(model.predict, X, algorithm="permutation")
        shap_values_original = explainer_original(X[:2])

        mlflow.shap.log_explainer(explainer_original, "test_explainer")

        explainer_pyfunc = mlflow.pyfunc.load_model("runs:/" + run_id + "/test_explainer")
        shap_values_new = explainer_pyfunc.predict(X[:2])

        np.testing.assert_allclose(shap_values_original.values, shap_values_new, rtol=100, atol=100)
