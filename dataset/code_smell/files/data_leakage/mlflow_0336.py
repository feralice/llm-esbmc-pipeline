# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L310-L322
# smelly line(s) in the original file: 316
# smelly line(s) in this file: 13
# ids: mlflow_0336
def test_tf_keras_autolog_log_datasets_with_validation_data_as_numpy_tuple(
    fashion_mnist_tf_dataset, fashion_mnist_tf_dataset_eval
):
    mlflow.tensorflow.autolog(log_datasets=True)
    fashion_mnist_model = _create_fashion_mnist_model()
    X_eval, y_eval = next(fashion_mnist_tf_dataset_eval.as_numpy_iterator())
    fashion_mnist_model.fit(fashion_mnist_tf_dataset, validation_data=(X_eval, y_eval))

    client = MlflowClient()
    dataset_inputs = client.get_run(mlflow.last_active_run().info.run_id).inputs.dataset_inputs
    assert len(dataset_inputs) == 2
    assert dataset_inputs[0].tags[0].value == "train"
    assert dataset_inputs[1].tags[0].value == "eval"
