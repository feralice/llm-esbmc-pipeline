# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/gluon/test_gluon_autolog.py#L195-L216
# smelly line(s) in the original file: 213
# smelly line(s) in this file: 25
# ids: mlflow_0218
def test_autolog_registering_model():
    registered_model_name = "test_autolog_registered_model"
    mlflow.gluon.autolog(registered_model_name=registered_model_name)

    data = DataLoader(LogsDataset(), batch_size=128, last_batch="discard")

    model = HybridSequential()
    model.add(Dense(64, activation="relu"))
    model.add(Dense(10))
    model.initialize()
    model.hybridize()

    trainer = Trainer(
        model.collect_params(), "adam", optimizer_params={"learning_rate": 0.001, "epsilon": 1e-07}
    )
    est = get_estimator(model, trainer)

    with mlflow.start_run():
        est.fit(data, epochs=3)

        registered_model = MlflowClient().get_registered_model(registered_model_name)
        assert registered_model.name == registered_model_name
