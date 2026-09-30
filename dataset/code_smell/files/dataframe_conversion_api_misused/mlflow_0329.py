# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/statsmodels/test_statsmodels_model_export.py#L397-L413
# smelly line(s) in the original file: 412
# smelly line(s) in this file: 22
# ids: mlflow_0329
def test_pyfunc_serve_and_score():
    model, _, inference_dataframe = ols_model()
    artifact_path = "model"
    with mlflow.start_run():
        mlflow.statsmodels.log_model(model, artifact_path)
        model_uri = mlflow.get_artifact_uri(artifact_path)

    resp = pyfunc_serve_and_score_model(
        model_uri,
        data=pd.DataFrame(inference_dataframe),
        content_type=pyfunc_scoring_server.CONTENT_TYPE_JSON,
        extra_args=EXTRA_PYFUNC_SERVING_TEST_ARGS,
    )
    scores = pd.DataFrame(
        data=json.loads(resp.content.decode("utf-8"))["predictions"]
    ).values.squeeze()
    np.testing.assert_array_almost_equal(scores, model.predict(inference_dataframe))
