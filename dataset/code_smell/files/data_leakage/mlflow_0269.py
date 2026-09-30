# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/shap/test_log.py#L358-L390
# smelly line(s) in the original file: 364
# smelly line(s) in this file: 13
# ids: mlflow_0269
def test_pyfunc_serve_and_score():
    # Note: this implementation of an identify function is only compatible with versions of
    # shap <= 0.41.0. A breaking change was introduced with how numba is used with shap in version
    # 0.42.0.
    X, y = get_housing_data()

    reg = sklearn.ensemble.RandomForestRegressor(n_estimators=10).fit(X, y)
    model = shap.Explainer(
        reg.predict,
        masker=X,
        algorithm="permutation",
        # `link` defaults to `shap.links.identity` which is decorated by `numba.jit` and causes
        # the following error when loading the explainer for serving:
        # ```
        # Exception: The passed link function needs to be callable and have a callable
        # .inverse property!
        # ```
        # As a workaround, use an identify function that's NOT decorated by `numba.jit`.
        link=create_identity_function(),
    )
    artifact_path = "model"
    with mlflow.start_run():
        mlflow.shap.log_explainer(model, artifact_path)
        model_uri = mlflow.get_artifact_uri(artifact_path)

    resp = pyfunc_serve_and_score_model(
        model_uri,
        data=pd.DataFrame(X[:3]),
        content_type=pyfunc_scoring_server.CONTENT_TYPE_JSON,
    )
    decoded_json = json.loads(resp.content.decode("utf-8"))
    scores = pd.DataFrame(data=decoded_json["predictions"]).values
    np.testing.assert_allclose(scores, model(X[:3]).values, rtol=100, atol=100)
