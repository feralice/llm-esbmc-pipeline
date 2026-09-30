# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L1066-L1084
# smelly line(s) in the original file: 1081
# smelly line(s) in this file: 22
# ids: mlflow_0355
def test_autolog_text_vec_model(tmp_path):
    """
    Verifies autolog successfully saves a model that can't be saved in the H5 format
    """
    mlflow.tensorflow.autolog()

    train_samples = np.array(["this is an example", "another example"])
    train_labels = np.array([0.4, 0.2])
    model = get_text_vec_model(train_samples)

    # Saving in the H5 format should fail
    with pytest.raises(NotImplementedError, match="is not supported in h5"):
        model.save(str(tmp_path.joinpath("model.h5")), save_format="h5")

    with mlflow.start_run() as run:
        model.fit(train_samples, train_labels, epochs=1)

    loaded_model = mlflow.tensorflow.load_model("runs:/" + run.info.run_id + "/model")
    np.testing.assert_array_equal(loaded_model.predict(train_samples), model.predict(train_samples))
