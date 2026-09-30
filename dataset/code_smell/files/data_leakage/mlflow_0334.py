# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L269-L293
# smelly line(s) in the original file: 274
# smelly line(s) in this file: 12
# ids: mlflow_0334
def test_tf_keras_autolog_log_datasets_configuration_with_tf_dataset(
    fashion_mnist_tf_dataset, log_datasets
):
    mlflow.tensorflow.autolog(log_datasets=log_datasets)
    fashion_mnist_model = _create_fashion_mnist_model()
    fashion_mnist_model.fit(fashion_mnist_tf_dataset)

    client = MlflowClient()
    dataset_inputs = client.get_run(mlflow.last_active_run().info.run_id).inputs.dataset_inputs
    if log_datasets:
        assert len(dataset_inputs) == 1
        numpy_data = next(fashion_mnist_tf_dataset.as_numpy_iterator())
        assert dataset_inputs[0].dataset.schema == json.dumps(
            {
                "mlflow_tensorspec": {
                    "features": _infer_schema(
                        {str(i): data_element for i, data_element in enumerate(numpy_data)}
                    ).to_json(),
                    "targets": None,
                }
            }
        )

    else:
        assert len(dataset_inputs) == 0
