# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pyfunc/test_pyfunc_schema_enforcement.py#L25-L39
# smelly line(s) in the original file: 28
# smelly line(s) in this file: 10
# ids: mlflow_0292
def test_schema_enforcement_single_column_2d_array():
    X = np.array([[1], [2], [3]])
    y = np.array([1, 2, 3])
    model = sklearn.linear_model.LinearRegression()
    model.fit(X, y)
    signature = infer_signature(X, y)
    assert signature.inputs.inputs[0].shape == (-1, 1)
    assert signature.outputs.inputs[0].shape == (-1,)

    with mlflow.start_run():
        model_info = mlflow.sklearn.log_model(model, "model", signature=signature)

    loaded_model = mlflow.pyfunc.load_model(model_info.model_uri)
    pdf = pd.DataFrame(X)
    np.testing.assert_almost_equal(loaded_model.predict(pdf), model.predict(pdf))
