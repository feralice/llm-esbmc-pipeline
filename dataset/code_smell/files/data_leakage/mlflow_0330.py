# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L173-L182
# smelly line(s) in the original file: 180
# smelly line(s) in this file: 14
# ids: mlflow_0330
def test_tf_keras_autolog_ends_auto_created_run(random_train_data, random_one_hot_labels):
    mlflow.tensorflow.autolog()

    data = random_train_data
    labels = random_one_hot_labels

    model = create_tf_keras_model()
    model.fit(data, labels, epochs=10)

    assert mlflow.active_run() is None
