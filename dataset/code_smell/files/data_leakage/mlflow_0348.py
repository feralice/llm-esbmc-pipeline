# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L644-L663
# smelly line(s) in the original file: 658
# smelly line(s) in this file: 21
# ids: mlflow_0348
def test_tf_keras_autolog_logs_metrics_for_single_epoch_training(
    random_train_data, random_one_hot_labels
):
    """
    tf.Keras exhibits inconsistent epoch indexing behavior in comparison with other
    TF2 APIs (e.g., tf.Estimator). tf.Keras uses zero-indexing for epochs,
    while other APIs use one-indexing. Accordingly, this test verifies that metrics are
    produced in the boundary case where a model is trained for a single epoch, ensuring
    that we don't miss the zero index in the tf.Keras case.
    """
    mlflow.tensorflow.autolog(every_n_iter=5)

    model = create_tf_keras_model()
    with mlflow.start_run() as run:
        model.fit(random_train_data, random_one_hot_labels, epochs=1)

    client = MlflowClient()
    run_metrics = client.get_run(run.info.run_id).data.metrics
    assert "accuracy" in run_metrics
    assert "loss" in run_metrics
