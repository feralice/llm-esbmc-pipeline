# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pyfunc/test_scoring_server.py#L99-L112
# smelly line(s) in the original file: 105
# smelly line(s) in this file: 13
# ids: mlflow_0305
def keras_model():
    iris = datasets.load_iris()
    data = pd.DataFrame(
        data=np.c_[iris["data"], iris["target"]], columns=iris["feature_names"] + ["target"]
    )
    y = data["target"]
    X = data.drop("target", axis=1).values
    input_a = Input(shape=(2,), name="a")
    input_b = Input(shape=(2,), name="b")
    output = Dense(1)(Dense(3, input_dim=4)(Concatenate()([input_a, input_b])))
    model = Model(inputs=[input_a, input_b], outputs=output)
    model.compile(loss="mean_squared_error", optimizer=SGD())
    model.fit([X[:, :2], X[:, -2:]], y)
    return ModelWithData(model=model, inference_data=X)
