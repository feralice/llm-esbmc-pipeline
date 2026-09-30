# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L967-L986
# smelly line(s) in the original file: 984
# smelly line(s) in this file: 24
# ids: mlflow_0354
def test_tf_keras_autolog_logs_to_and_deletes_temporary_directory_when_tensorboard_callback_absent(
    tmp_path, random_train_data, random_one_hot_labels
):
    from mlflow.tensorflow import _TensorBoardLogDir

    mlflow.tensorflow.autolog()

    mock_log_dir_inst = _TensorBoardLogDir(
        location=str(tmp_path.joinpath("tb_logging")), is_temp=True
    )
    with patch("mlflow.tensorflow._TensorBoardLogDir", autospec=True) as mock_log_dir_class:
        mock_log_dir_class.return_value = mock_log_dir_inst

        data = random_train_data
        labels = random_one_hot_labels

        model = create_tf_keras_model()
        model.fit(data, labels, epochs=10)

        assert not os.path.exists(mock_log_dir_inst.location)
