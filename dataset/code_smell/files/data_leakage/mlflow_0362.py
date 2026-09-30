# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1248-L1257
# smelly line(s) in the original file: 1252
# smelly line(s) in this file: 11
# ids: mlflow_0362
def test_keras_autolog_infers_model_signature_correctly_with_tf_dataset(fashion_mnist_tf_dataset):
    mlflow.tensorflow.autolog(log_model_signatures=True)
    fashion_mnist_model = _create_fashion_mnist_model()
    with mlflow.start_run() as run:
        fashion_mnist_model.fit(fashion_mnist_tf_dataset)
        _assert_autolog_infers_model_signature_correctly(
            run,
            [{"type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1, 28, 28]}}],
            [{"type": "tensor", "tensor-spec": {"dtype": "float32", "shape": [-1, 10]}}],
        )
