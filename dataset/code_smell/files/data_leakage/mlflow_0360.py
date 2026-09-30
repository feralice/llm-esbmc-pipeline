# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1214-L1225
# smelly line(s) in the original file: 1220
# smelly line(s) in this file: 13
# ids: mlflow_0360
def test_keras_autolog_infers_model_signature_correctly_with_nparray(
    random_train_data, random_one_hot_labels
):
    mlflow.tensorflow.autolog(log_model_signatures=True)
    initial_model = create_tf_keras_model()
    with mlflow.start_run() as run:
        initial_model.fit(random_train_data, random_one_hot_labels)
        _assert_autolog_infers_model_signature_correctly(
            run,
            [{"type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1, 4]}}],
            [{"type": "tensor", "tensor-spec": {"dtype": "float32", "shape": [-1, 3]}}],
        )
