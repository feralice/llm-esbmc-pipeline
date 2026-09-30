# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L118-L125
# smelly line(s) in the original file: 119, 121
# smelly line(s) in this file: 8, 10
# ids: mlflow_0370, mlflow_0371
def _create_fashion_mnist_model():
    model = tf.keras.Sequential([tf.keras.layers.Flatten(), tf.keras.layers.Dense(10)])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )
    return model
