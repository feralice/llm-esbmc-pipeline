# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L699-L737
# smelly line(s) in the original file: 732
# smelly line(s) in this file: 40
# ids: mlflow_0350
def get_tf_keras_random_data_run_with_callback(
    random_train_data,
    random_one_hot_labels,
    callback,
    restore_weights,
    patience,
    initial_epoch,
    log_models,
):
    # pylint: disable=unused-argument
    mlflow.tensorflow.autolog(every_n_iter=1, log_models=log_models)

    data = random_train_data
    labels = random_one_hot_labels

    model = create_tf_keras_model()
    if callback == "early":
        # min_delta is set as such to guarantee early stopping
        callback = tf.keras.callbacks.EarlyStopping(
            monitor="loss",
            patience=patience,
            min_delta=99999999,
            restore_best_weights=restore_weights,
            verbose=1,
        )
    else:

        class CustomCallback(tf.keras.callbacks.Callback):
            def on_train_end(self, logs=None):
                pass

        callback = CustomCallback()

    history = model.fit(
        data, labels, epochs=initial_epoch + 10, callbacks=[callback], initial_epoch=initial_epoch
    )

    client = MlflowClient()
    return client.get_run(client.search_runs(["0"])[0].info.run_id), history, callback
