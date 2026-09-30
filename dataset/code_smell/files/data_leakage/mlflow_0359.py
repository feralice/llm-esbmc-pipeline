# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1204-L1211
# smelly line(s) in the original file: 1210
# smelly line(s) in this file: 13
# ids: mlflow_0359
def test_keras_autolog_input_example_load_and_predict_with_nparray(
    random_train_data, random_one_hot_labels
):
    mlflow.tensorflow.autolog(log_input_examples=True, log_model_signatures=True)
    initial_model = create_tf_keras_model()
    with mlflow.start_run() as run:
        initial_model.fit(random_train_data, random_one_hot_labels)
        _assert_keras_autolog_input_example_load_and_predict_with_nparray(run, random_train_data)
