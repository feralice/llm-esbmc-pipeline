# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/models/test_signature.py#L167-L176
# smelly line(s) in the original file: 170
# smelly line(s) in this file: 10
# ids: mlflow_0314
def test_set_signature_to_saved_model(tmp_path):
    model_path = str(tmp_path)
    mlflow.sklearn.save_model(
        RandomForestRegressor(),
        model_path,
        serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE,
    )
    signature = infer_signature(np.array([1]))
    set_signature(model_path, signature)
    assert Model.load(model_path).signature == signature
