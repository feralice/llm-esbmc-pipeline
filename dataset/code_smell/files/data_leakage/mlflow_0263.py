# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/shap/test_log.py#L42-L75
# smelly line(s) in the original file: 53
# smelly line(s) in this file: 18
# ids: mlflow_0263
def test_sklearn_log_explainer():
    """
    Tests mlflow.shap log_explainer with mlflow serialization of the underlying model
    """

    with mlflow.start_run() as run:
        run_id = run.info.run_id

        X, y = get_housing_data()

        model = sklearn.ensemble.RandomForestRegressor(n_estimators=100)
        model.fit(X, y)

        explainer_original = shap.Explainer(model.predict, X, algorithm="permutation")
        shap_values_original = explainer_original(X[:5])

        mlflow.shap.log_explainer(explainer_original, "test_explainer")

        explainer_uri = "runs:/" + run_id + "/test_explainer"

        explainer_loaded = mlflow.shap.load_explainer(explainer_uri)
        shap_values_new = explainer_loaded(X[:5])

        explainer_path = _download_artifact_from_uri(artifact_uri=explainer_uri)
        flavor_conf = _get_flavor_configuration(
            model_path=explainer_path, flavor_name=mlflow.shap.FLAVOR_NAME
        )
        underlying_model_flavor = flavor_conf["underlying_model_flavor"]

        assert underlying_model_flavor == mlflow.sklearn.FLAVOR_NAME
        np.testing.assert_array_equal(shap_values_original.base_values, shap_values_new.base_values)
        np.testing.assert_allclose(
            shap_values_original.values, shap_values_new.values, rtol=100, atol=100
        )
