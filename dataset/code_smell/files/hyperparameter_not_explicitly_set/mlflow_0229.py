# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/gluon/test_gluon_model_export.py#L82-L100
# smelly line(s) in the original file: 89
# smelly line(s) in this file: 14
# ids: mlflow_0229
def gluon_model(model_data):
    train_data, train_label, _ = model_data
    dataset = mx.gluon.data.ArrayDataset(train_data, train_label)
    train_data_loader = DataLoader(dataset, batch_size=128, last_batch="discard")
    model = HybridSequential()
    model.add(Dense(128, activation="relu"))
    model.add(Dense(64, activation="relu"))
    model.add(Dense(10))
    model.initialize()
    model.hybridize()
    trainer = Trainer(
        model.collect_params(), "adam", optimizer_params={"learning_rate": 0.001, "epsilon": 1e-07}
    )

    est = get_estimator(model, trainer)

    est.fit(train_data_loader, epochs=3)

    return model
