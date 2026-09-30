# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L359-L372
# smelly line(s) in the original file: 367
# smelly line(s) in this file: 15
# ids: mlflow_0339
def tf_keras_random_data_run(random_train_data, random_one_hot_labels, initial_epoch):
    # pylint: disable=unused-argument
    mlflow.tensorflow.autolog()

    data = random_train_data
    labels = random_one_hot_labels

    model = create_tf_keras_model()
    history = model.fit(
        data, labels, epochs=initial_epoch + 10, steps_per_epoch=1, initial_epoch=initial_epoch
    )

    client = MlflowClient()
    return client.get_run(client.search_runs(["0"])[0].info.run_id), history
