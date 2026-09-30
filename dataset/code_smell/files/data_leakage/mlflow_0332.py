# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L207-L234
# smelly line(s) in the original file: 217
# smelly line(s) in this file: 17
# ids: mlflow_0332
def test_tf_keras_autolog_log_datasets_configuration_with_numpy(
    random_train_data, random_one_hot_labels, log_datasets
):
    mlflow.tensorflow.autolog(log_datasets=log_datasets)

    data = random_train_data
    labels = random_one_hot_labels

    model = create_tf_keras_model()

    model.fit(data, labels, epochs=10)

    client = MlflowClient()
    dataset_inputs = client.get_run(mlflow.last_active_run().info.run_id).inputs.dataset_inputs
    if log_datasets:
        assert len(dataset_inputs) == 1
        feature_schema = _infer_schema(data)
        target_schema = _infer_schema(labels)
        assert dataset_inputs[0].dataset.schema == json.dumps(
            {
                "mlflow_tensorspec": {
                    "features": feature_schema.to_json(),
                    "targets": target_schema.to_json(),
                }
            }
        )
    else:
        assert len(dataset_inputs) == 0
