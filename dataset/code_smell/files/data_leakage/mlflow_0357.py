# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1098-L1120
# smelly line(s) in the original file: 1111
# smelly line(s) in this file: 20
# ids: mlflow_0357
def test_fluent_autolog_with_tf_keras_logs_expected_content(
    random_train_data, random_one_hot_labels
):
    """
    Guards against previously-exhibited issues where using the fluent `mlflow.autolog()` API with
    `tf.keras` Models did not work due to conflicting patches set by both the
    `mlflow.tensorflow.autolog()` and the `mlflow.keras.autolog()` APIs.
    """
    mlflow.autolog()

    model = create_tf_keras_model()

    with mlflow.start_run() as run:
        model.fit(random_train_data, random_one_hot_labels, epochs=10)

    client = MlflowClient()
    run_data = client.get_run(run.info.run_id).data
    assert "accuracy" in run_data.metrics
    assert "epochs" in run_data.params

    artifacts = client.list_artifacts(run.info.run_id)
    artifacts = (x.path for x in artifacts)
    assert "model" in artifacts
