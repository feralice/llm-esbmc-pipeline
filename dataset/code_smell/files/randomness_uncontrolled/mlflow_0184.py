# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/evaluate/test_evaluation.py#L277-L288
# smelly line(s) in the original file: 279
# smelly line(s) in this file: 9
# ids: mlflow_0184
def multiclass_logistic_regressor_model_uri_by_max_iter(max_iter):
    X, y = get_iris()
    clf = sklearn.linear_model.LogisticRegression(max_iter=max_iter)
    clf.fit(X, y)

    with mlflow.start_run() as run:
        mlflow.sklearn.log_model(clf, f"clf_model_{max_iter}_iters")
        multiclass_logistic_regressor_model_uri = get_artifact_uri(
            run.info.run_id, f"clf_model_{max_iter}_iters"
        )

    return multiclass_logistic_regressor_model_uri
