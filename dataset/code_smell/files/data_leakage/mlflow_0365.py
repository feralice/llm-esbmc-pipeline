# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1295-L1302
# smelly line(s) in the original file: 1299
# smelly line(s) in this file: 11
# ids: mlflow_0365
def test_keras_autolog_input_example_load_and_predict_with_keras_sequence(keras_data_gen_sequence):
    mlflow.tensorflow.autolog(log_input_examples=True, log_model_signatures=True)
    model = create_tf_keras_model()
    with mlflow.start_run() as run:
        model.fit(keras_data_gen_sequence)
        _assert_keras_autolog_input_example_load_and_predict_with_nparray(
            run, keras_data_gen_sequence[:][0][:5]
        )
