# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/shap/test_log.py#L163-L177
# smelly line(s) in the original file: 167
# smelly line(s) in this file: 11
# ids: mlflow_0267
def test_load_pyfunc(tmp_path):
    X, y = get_housing_data()

    model = sklearn.ensemble.RandomForestRegressor(n_estimators=100)
    model.fit(X, y)

    explainer_original = shap.Explainer(model.predict, X, algorithm="permutation")
    shap_values_original = explainer_original(X[:2])
    path = str(tmp_path.joinpath("pyfunc_test"))
    mlflow.shap.save_explainer(explainer_original, path)

    explainer_pyfunc = mlflow.shap._load_pyfunc(path)
    shap_values_new = explainer_pyfunc.predict(X[:2])

    np.testing.assert_allclose(shap_values_original.values, shap_values_new, rtol=100, atol=100)
