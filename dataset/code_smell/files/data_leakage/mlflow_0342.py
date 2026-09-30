# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L538-L555
# smelly line(s) in the original file: 550, 554
# smelly line(s) in this file: 19, 23
# ids: mlflow_0342, mlflow_0343
def test_tf_keras_autolog_implicit_batch_size_works_multi_input(generate_data, batch_size):
    mlflow.tensorflow.autolog()

    input1 = tf.keras.Input(shape=(1,))
    input2 = tf.keras.Input(shape=(1,))
    concat = tf.keras.layers.Concatenate()([input1, input2])
    output = tf.keras.layers.Dense(1, activation="sigmoid")(concat)

    model = tf.keras.models.Model(inputs=[input1, input2], outputs=output)
    model.compile(loss="mse")

    # 'x' passed as arg
    model.fit(generate_data(batch_size), verbose=0)
    assert mlflow.last_active_run().data.params["batch_size"] == str(batch_size)

    # 'x' passed as kwarg
    model.fit(x=generate_data(batch_size), verbose=0)
    assert mlflow.last_active_run().data.params["batch_size"] == str(batch_size)
