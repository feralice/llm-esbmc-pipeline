# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L921-L945
# smelly line(s) in the original file: 940, 942
# smelly line(s) in this file: 26, 28
# ids: mlflow_0351, mlflow_0352
def test_tf_keras_autolog_does_not_mutate_original_callbacks_list(
    tmp_path, random_train_data, random_one_hot_labels, positional
):
    """
    TensorFlow autologging passes new callbacks to the `fit()` / `fit_generator()` function. If
    preexisting user-defined callbacks already exist, these new callbacks are added to the
    user-specified ones. This test verifies that the new callbacks are added to the without
    permanently mutating the original list of callbacks.
    """
    mlflow.tensorflow.autolog()

    tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=tmp_path)
    callbacks = [tensorboard_callback]

    model = create_tf_keras_model()
    data = random_train_data
    labels = random_one_hot_labels

    if positional:
        model.fit(data, labels, None, 10, 1, callbacks)
    else:
        model.fit(data, labels, epochs=10, callbacks=callbacks)

    assert len(callbacks) == 1
    assert callbacks == [tensorboard_callback]
