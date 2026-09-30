# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1305-L1316
# smelly line(s) in the original file: 1311
# smelly line(s) in this file: 13
# ids: mlflow_0366
def test_keras_autolog_infers_model_signature_correctly_with_keras_sequence(
    keras_data_gen_sequence,
):
    mlflow.tensorflow.autolog(log_model_signatures=True)
    initial_model = create_tf_keras_model()
    with mlflow.start_run() as run:
        initial_model.fit(keras_data_gen_sequence)
        _assert_autolog_infers_model_signature_correctly(
            run,
            [{"type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1, 4]}}],
            [{"type": "tensor", "tensor-spec": {"dtype": "float32", "shape": [-1, 3]}}],
        )
