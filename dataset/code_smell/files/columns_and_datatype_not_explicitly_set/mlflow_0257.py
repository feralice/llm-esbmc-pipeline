# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/lightgbm/test_lightgbm_autolog.py#L216-L259
# smelly line(s) in the original file: 252
# smelly line(s) in this file: 43
# ids: mlflow_0257
def test_lgb_autolog_with_sklearn_outputs_do_not_reflect_training_dataset_mutations():
    original_lgb_classifier_fit = lgb.LGBMClassifier.fit
    original_lgb_classifier_predict = lgb.LGBMClassifier.predict

    def patched_lgb_classifier_fit(self, *args, **kwargs):
        X = args[0]
        X["TESTCOL"] = 5
        return original_lgb_classifier_fit(self, *args, **kwargs)

    def patched_lgb_classifier_predict(self, *args, **kwargs):
        X = args[0]
        X["TESTCOL"] = 5
        return original_lgb_classifier_predict(self, *args, **kwargs)

    with mock.patch("lightgbm.LGBMClassifier.fit", patched_lgb_classifier_fit), mock.patch(
        "lightgbm.LGBMClassifier.predict", patched_lgb_classifier_predict
    ):
        mlflow.lightgbm.autolog(log_models=True, log_model_signatures=True, log_input_examples=True)

        X = pd.DataFrame(
            {
                "Total Volume": [64236.62, 54876.98, 118220.22],
                "Total Bags": [8696.87, 9505.56, 8145.35],
                "Small Bags": [8603.62, 9408.07, 8042.21],
                "Large Bags": [93.25, 97.49, 103.14],
                "XLarge Bags": [0.0, 0.0, 0.0],
            }
        )
        y = pd.Series([1, 0, 1])

        params = {"n_estimators": 10, "reg_lambda": 1}
        model = lgb.LGBMClassifier(**params)
        model.fit(X, y)

        run_artifact_uri = mlflow.last_active_run().info.artifact_uri
        model_conf = get_model_conf(run_artifact_uri)
        input_example = pd.read_json(
            os.path.join(run_artifact_uri, "model", "input_example.json"), orient="split"
        )
        model_signature_input_names = [inp.name for inp in model_conf.signature.inputs.inputs]
        assert "XLarge Bags" in model_signature_input_names
        assert "XLarge Bags" in input_example.columns
        assert "TESTCOL" not in model_signature_input_names
        assert "TESTCOL" not in input_example.columns
