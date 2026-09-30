# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/xgboost/test_xgboost_autolog.py#L220-L266
# smelly line(s) in the original file: 259
# smelly line(s) in this file: 46
# ids: mlflow_0377
def test_xgb_autolog_with_sklearn_outputs_do_not_reflect_training_dataset_mutations():
    original_xgb_regressor_fit = xgb.XGBRegressor.fit
    original_xgb_regressor_predict = xgb.XGBRegressor.predict

    def patched_xgb_regressor_fit(self, *args, **kwargs):
        X = args[0]
        X["TESTCOL"] = 5
        return original_xgb_regressor_fit(self, *args, **kwargs)

    def patched_xgb_regressor_predict(self, *args, **kwargs):
        X = args[0]
        X["TESTCOL"] = 5
        return original_xgb_regressor_predict(self, *args, **kwargs)

    with mock.patch("xgboost.XGBRegressor.fit", patched_xgb_regressor_fit), mock.patch(
        "xgboost.XGBRegressor.predict", patched_xgb_regressor_predict
    ):
        xgb.XGBRegressor.fit = patched_xgb_regressor_fit
        xgb.XGBRegressor.predict = patched_xgb_regressor_predict

        mlflow.xgboost.autolog(log_models=True, log_model_signatures=True, log_input_examples=True)

        X = pd.DataFrame(
            {
                "Total Volume": [64236.62, 54876.98, 118220.22],
                "Total Bags": [8696.87, 9505.56, 8145.35],
                "Small Bags": [8603.62, 9408.07, 8042.21],
                "Large Bags": [93.25, 97.49, 103.14],
                "XLarge Bags": [0.0, 0.0, 0.0],
            }
        )
        y = pd.Series([1.33, 1.35, 0.93])

        params = {"n_estimators": 10, "reg_lambda": 1}
        model = xgb.XGBRegressor(**params)
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
