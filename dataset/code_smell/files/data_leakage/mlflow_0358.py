# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1136-L1146
# smelly line(s) in the original file: 1144
# smelly line(s) in this file: 15
# ids: mlflow_0358
def test_tf_keras_autolog_distributed_training(random_train_data, random_one_hot_labels):
    # Ref: https://www.tensorflow.org/tutorials/distribute/keras
    mlflow.tensorflow.autolog()

    with tf.distribute.MirroredStrategy().scope():
        model = create_tf_keras_model()
    fit_params = {"epochs": 10, "batch_size": 10}
    with mlflow.start_run() as run:
        model.fit(random_train_data, random_one_hot_labels, **fit_params)
    client = MlflowClient()
    assert client.get_run(run.info.run_id).data.params.keys() >= fit_params.keys()
