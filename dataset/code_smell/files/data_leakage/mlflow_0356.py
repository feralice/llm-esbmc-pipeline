# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1087-L1095
# smelly line(s) in the original file: 1092
# smelly line(s) in this file: 12
# ids: mlflow_0356
def test_tf_keras_model_autolog_registering_model(random_train_data, random_one_hot_labels):
    registered_model_name = "test_autolog_registered_model"
    mlflow.tensorflow.autolog(registered_model_name=registered_model_name)
    with mlflow.start_run():
        model = create_tf_keras_model()
        model.fit(random_train_data, random_one_hot_labels, epochs=10)

        registered_model = MlflowClient().get_registered_model(registered_model_name)
        assert registered_model.name == registered_model_name
