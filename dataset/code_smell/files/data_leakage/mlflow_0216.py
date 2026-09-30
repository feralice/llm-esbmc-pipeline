# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/gluon/test_gluon_autolog.py#L144-L163
# smelly line(s) in the original file: 161
# smelly line(s) in this file: 24
# ids: mlflow_0216
def test_autolog_ends_auto_created_run():
    mlflow.gluon.autolog()

    data = DataLoader(LogsDataset(), batch_size=128, last_batch="discard")

    model = HybridSequential()
    model.add(Dense(64, activation="relu"))
    model.add(Dense(64, activation="relu"))
    model.add(Dense(10))
    model.initialize()
    model.hybridize()

    trainer = Trainer(
        model.collect_params(), "adam", optimizer_params={"learning_rate": 0.001, "epsilon": 1e-07}
    )
    est = get_estimator(model, trainer)

    est.fit(data, epochs=3)

    assert mlflow.active_run() is None
