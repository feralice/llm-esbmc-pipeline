# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1260-L1273
# smelly line(s) in the original file: 1266
# smelly line(s) in this file: 13
# ids: mlflow_0363
def test_keras_autolog_input_example_load_and_predict_with_dict(
    random_train_dict_mapping, random_one_hot_labels
):
    mlflow.tensorflow.autolog(log_input_examples=True, log_model_signatures=True)
    model = _create_model_for_dict_mapping()
    with mlflow.start_run() as run:
        model.fit(random_train_dict_mapping, random_one_hot_labels)
        model_path = os.path.join(run.info.artifact_uri, "model")
        model_conf = Model.load(os.path.join(model_path, "MLmodel"))
        input_example = _read_example(model_conf, model_path)
        for k, v in random_train_dict_mapping.items():
            np.testing.assert_array_almost_equal(input_example[k], np.take(v, range(0, 5)))
        pyfunc_model = mlflow.pyfunc.load_model(os.path.join(run.info.artifact_uri, "model"))
        pyfunc_model.predict(input_example)
