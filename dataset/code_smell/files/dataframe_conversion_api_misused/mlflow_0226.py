# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/gluon/test_gluon_model_export.py#L103-L119
# smelly line(s) in the original file: 118
# smelly line(s) in this file: 22
# ids: mlflow_0226
def test_model_save_load(gluon_model, model_data, model_path):
    _, _, test_data = model_data
    expected = array_module.argmax(gluon_model(test_data), axis=1)

    mlflow.gluon.save_model(gluon_model, model_path)
    # Loading Gluon model
    model_loaded = mlflow.gluon.load_model(model_path, ctx.cpu())
    actual = array_module.argmax(model_loaded(test_data), axis=1)
    assert all(expected == actual)
    # Loading pyfunc model
    pyfunc_loaded = mlflow.pyfunc.load_model(model_path)
    test_pyfunc_data = pd.DataFrame(test_data.asnumpy())
    pyfunc_preds = pyfunc_loaded.predict(test_pyfunc_data)
    assert all(np.argmax(pyfunc_preds.values, axis=1) == expected.asnumpy())
    # test with numpy array input
    pyfunc_preds = pyfunc_loaded.predict(test_pyfunc_data.values)
    assert all(np.argmax(pyfunc_preds, axis=1) == expected.asnumpy())
