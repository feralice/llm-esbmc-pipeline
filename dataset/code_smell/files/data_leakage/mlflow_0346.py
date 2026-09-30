# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L593-L620
# smelly line(s) in the original file: 618
# smelly line(s) in this file: 32
# ids: mlflow_0346
def test_tf_keras_autolog_succeeds_for_tf_datasets_lacking_batch_size_info():
    X_train = np.random.rand(100, 100)
    y_train = np.random.randint(0, 10, 100)

    train_ds = tf.data.Dataset.from_tensor_slices((X_train, y_train))
    train_ds = train_ds.batch(50)
    train_ds = train_ds.cache().prefetch(buffer_size=5)
    assert not hasattr(train_ds, "_batch_size")

    model = tf.keras.Sequential()
    model.add(
        tf.keras.Input(
            100,
        )
    )
    model.add(tf.keras.layers.Dense(256, activation="relu"))
    model.add(tf.keras.layers.Dropout(rate=0.4))
    model.add(tf.keras.layers.Dense(10, activation="sigmoid"))
    model.compile(
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=False),
        optimizer="Adam",
        metrics=["accuracy"],
    )

    mlflow.tensorflow.autolog()
    model.fit(train_ds, epochs=100)

    assert mlflow.last_active_run().data.params["batch_size"] == "None"
