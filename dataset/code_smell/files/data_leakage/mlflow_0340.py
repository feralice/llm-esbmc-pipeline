# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L464-L476
# smelly line(s) in the original file: 471, 475
# smelly line(s) in this file: 14, 18
# ids: mlflow_0340, mlflow_0341
def test_tf_keras_autolog_implicit_batch_size_works(generate_data, batch_size):
    mlflow.autolog()
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Dense(1, input_shape=(1,)))
    model.compile(loss="mse")

    # 'x' passed as arg
    model.fit(generate_data(batch_size), verbose=0)
    assert mlflow.last_active_run().data.params["batch_size"] == str(batch_size)

    # 'x' passed as kwarg
    model.fit(x=generate_data(batch_size), verbose=0)
    assert mlflow.last_active_run().data.params["batch_size"] == str(batch_size)
