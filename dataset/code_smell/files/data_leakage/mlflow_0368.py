# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1328-L1347
# smelly line(s) in the original file: 1331
# smelly line(s) in this file: 10
# ids: mlflow_0368
def test_keras_autolog_logs_model_signature_by_default(keras_data_gen_sequence):
    mlflow.autolog()
    initial_model = create_tf_keras_model()
    initial_model.fit(keras_data_gen_sequence)

    mlmodel_path = mlflow.artifacts.download_artifacts(
        f"runs:/{mlflow.last_active_run().info.run_id}/model/MLmodel"
    )
    mlmodel_contents = yaml.safe_load(open(mlmodel_path))
    assert "signature" in mlmodel_contents.keys()
    signature = mlmodel_contents["signature"]
    assert signature is not None
    assert "inputs" in signature
    assert "outputs" in signature
    assert json.loads(signature["inputs"]) == [
        {"type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1, 4]}}
    ]
    assert json.loads(signature["outputs"]) == [
        {"type": "tensor", "tensor-spec": {"dtype": "float32", "shape": [-1, 3]}}
    ]
