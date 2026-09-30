# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1319-L1325
# smelly line(s) in the original file: 1323
# smelly line(s) in this file: 11
# ids: mlflow_0367
def test_keras_autolog_load_saved_hdf5_model(keras_data_gen_sequence):
    mlflow.tensorflow.autolog(keras_model_kwargs={"save_format": "h5"})
    model = create_tf_keras_model()
    with mlflow.start_run() as run:
        model.fit(keras_data_gen_sequence)
        mlflow.tensorflow.load_model(f"runs:/{run.info.run_id}/model")
        assert Path(run.info.artifact_uri, "model", "data", "model.h5").exists()
