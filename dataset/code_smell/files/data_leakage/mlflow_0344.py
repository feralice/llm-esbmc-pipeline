# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tensorflow/test_tensorflow2_autolog.py#L564-L590
# smelly line(s) in the original file: 584, 587
# smelly line(s) in this file: 27, 30
# ids: mlflow_0344, mlflow_0345
def test_tf_keras_autolog_implicit_batch_size_for_generator_dataset_without_side_effects(
    generator,
    batch_size,
):
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Dense

    data = np.array([[1, 2, 3], [3, 2, 1], [2, 2, 2], [10, 20, 30], [30, 20, 10], [20, 20, 20]])
    target = np.array([[1], [3], [2], [11], [13], [12]])

    model = Sequential()
    model.add(
        Dense(
            5, input_dim=3, activation="relu", kernel_initializer="zeros", bias_initializer="zeros"
        )
    )
    model.add(Dense(1, kernel_initializer="zeros", bias_initializer="zeros"))
    model.compile(loss="mae", optimizer="adam", metrics=["mse"])

    mlflow.autolog()
    actual_mse = model.fit(generator(data, target, batch_size), verbose=0).history["mse"][-1]

    mlflow.autolog(disable=True)
    expected_mse = model.fit(generator(data, target, batch_size), verbose=0).history["mse"][-1]

    np.testing.assert_allclose(actual_mse, expected_mse, atol=1)
    assert mlflow.last_active_run().data.params["batch_size"] == str(batch_size)
