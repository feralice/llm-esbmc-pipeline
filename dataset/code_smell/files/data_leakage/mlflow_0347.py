# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L623-L641
# smelly line(s) in the original file: 630
# smelly line(s) in this file: 14
# ids: mlflow_0347
def test_tf_keras_autolog_records_metrics_for_last_epoch(random_train_data, random_one_hot_labels):
    every_n_iter = 5
    num_training_epochs = 17
    mlflow.tensorflow.autolog(every_n_iter=every_n_iter)

    model = create_tf_keras_model()
    with mlflow.start_run() as run:
        model.fit(
            random_train_data,
            random_one_hot_labels,
            epochs=num_training_epochs,
            initial_epoch=0,
        )

    client = MlflowClient()
    run_metrics = client.get_run(run.info.run_id).data.metrics
    assert "accuracy" in run_metrics
    all_epoch_acc = client.get_metric_history(run.info.run_id, "accuracy")
    assert {metric.step for metric in all_epoch_acc} == {0, 5, 10, 15}
