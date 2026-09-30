# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L186-L203
# smelly line(s) in the original file: 197
# smelly line(s) in this file: 18
# ids: mlflow_0331
def test_tf_keras_autolog_log_models_configuration(
    random_train_data, random_one_hot_labels, log_models
):
    # pylint: disable=unused-argument
    mlflow.tensorflow.autolog(log_models=log_models)

    data = random_train_data
    labels = random_one_hot_labels

    model = create_tf_keras_model()

    model.fit(data, labels, epochs=10)

    client = MlflowClient()
    run_id = client.search_runs(["0"])[0].info.run_id
    artifacts = client.list_artifacts(run_id)
    artifacts = (x.path for x in artifacts)
    assert ("model" in artifacts) == log_models
