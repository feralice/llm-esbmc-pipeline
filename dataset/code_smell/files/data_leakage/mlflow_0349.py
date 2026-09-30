# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L666-L683
# smelly line(s) in the original file: 678
# smelly line(s) in this file: 19
# ids: mlflow_0349
def test_tf_keras_autolog_names_positional_parameters_correctly(
    random_train_data, random_one_hot_labels
):
    mlflow.tensorflow.autolog(every_n_iter=5)

    data = random_train_data
    labels = random_one_hot_labels

    model = create_tf_keras_model()

    with mlflow.start_run():
        # Pass `batch_size` as a positional argument for testing purposes
        model.fit(data, labels, 8, epochs=10, steps_per_epoch=1)
        run_id = mlflow.active_run().info.run_id

    client = MlflowClient()
    run_info = client.get_run(run_id)
    assert run_info.data.params.get("batch_size") == "8"
