# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L948-L964
# smelly line(s) in the original file: 962
# smelly line(s) in this file: 21
# ids: mlflow_0353
def test_tf_keras_autolog_does_not_delete_logging_directory_for_tensorboard_callback(
    tmp_path, random_train_data, random_one_hot_labels
):
    tensorboard_callback_logging_dir_path = str(tmp_path.joinpath("tb_logs"))
    tensorboard_callback = tf.keras.callbacks.TensorBoard(
        tensorboard_callback_logging_dir_path, histogram_freq=0
    )

    mlflow.tensorflow.autolog()

    data = random_train_data
    labels = random_one_hot_labels

    model = create_tf_keras_model()
    model.fit(data, labels, epochs=10, callbacks=[tensorboard_callback])

    assert os.path.exists(tensorboard_callback_logging_dir_path)
