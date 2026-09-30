# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1276-L1292
# smelly line(s) in the original file: 1282
# smelly line(s) in this file: 13
# ids: mlflow_0364
def test_keras_autolog_infers_model_signature_correctly_with_dict(
    random_train_dict_mapping, random_one_hot_labels
):
    mlflow.tensorflow.autolog(log_model_signatures=True)
    model = _create_model_for_dict_mapping()
    with mlflow.start_run() as run:
        model.fit(random_train_dict_mapping, random_one_hot_labels)
        _assert_autolog_infers_model_signature_correctly(
            run,
            [
                {"name": "a", "type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1]}},
                {"name": "b", "type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1]}},
                {"name": "c", "type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1]}},
                {"name": "d", "type": "tensor", "tensor-spec": {"dtype": "float64", "shape": [-1]}},
            ],
            [{"type": "tensor", "tensor-spec": {"dtype": "float32", "shape": [-1, 3]}}],
        )
