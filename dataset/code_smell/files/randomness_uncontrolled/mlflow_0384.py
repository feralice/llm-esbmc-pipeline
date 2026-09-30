# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/rapids/mlflow_project/src/rf_test/train.py#L33-L70
# smelly line(s) in the original file: 45
# smelly line(s) in this file: 19
# ids: mlflow_0384
def _train(params, fpath, hyperopt=False):
    """
    :param params: hyperparameters. Its structure is consistent with how search space is defined. See below.
    :param fpath: Path or URL for the training data used with the model.
    :param hyperopt: Use hyperopt for hyperparameter search during training.
    :return: dict with fields 'loss' (scalar loss) and 'status' (success/failure status of run)
    """
    max_depth, max_features, n_estimators = params
    max_depth, max_features, n_estimators = (int(max_depth), float(max_features), int(n_estimators))

    X_train, X_test, y_train, y_test = load_data(fpath)

    mod = RandomForestClassifier(
        max_depth=max_depth, max_features=max_features, n_estimators=n_estimators
    )

    mod.fit(X_train, y_train)
    preds = mod.predict(X_test)
    acc = accuracy_score(y_test, preds)

    mlparams = {
        "max_depth": str(max_depth),
        "max_features": str(max_features),
        "n_estimators": str(n_estimators),
    }
    mlflow.log_params(mlparams)

    mlflow.log_metric("accuracy", acc)

    predictions = mod.predict(X_train)
    signature = infer_signature(X_train, predictions)

    mlflow.sklearn.log_model(mod, "saved_models", signature=signature)

    if not hyperopt:
        return mod

    return {"loss": acc, "status": STATUS_OK}
