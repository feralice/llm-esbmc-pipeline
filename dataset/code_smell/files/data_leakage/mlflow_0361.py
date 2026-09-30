# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1232-L1241
# smelly line(s) in the original file: 1236
# smelly line(s) in this file: 11
# ids: mlflow_0361
def test_keras_autolog_input_example_load_and_predict_with_tf_dataset(fashion_mnist_tf_dataset):
    mlflow.tensorflow.autolog(log_input_examples=True, log_model_signatures=True)
    fashion_mnist_model = _create_fashion_mnist_model()
    with mlflow.start_run() as run:
        fashion_mnist_model.fit(fashion_mnist_tf_dataset)
        model_path = os.path.join(run.info.artifact_uri, "model")
        model_conf = Model.load(os.path.join(model_path, "MLmodel"))
        input_example = _read_example(model_conf, model_path)
        pyfunc_model = mlflow.pyfunc.load_model(os.path.join(run.info.artifact_uri, "model"))
        pyfunc_model.predict(input_example)
