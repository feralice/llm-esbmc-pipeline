# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L162-L170
# smelly line(s) in the original file: 168
# smelly line(s) in this file: 13
# ids: mlflow_0372
def create_tf_keras_model():
    model = tf.keras.Sequential()
    model.add(layers.Dense(16, activation="relu", input_shape=(4,)))
    model.add(layers.Dense(3, activation="softmax"))

    model.compile(
        optimizer=tf.keras.optimizers.Adam(), loss="categorical_crossentropy", metrics=["accuracy"]
    )
    return model
