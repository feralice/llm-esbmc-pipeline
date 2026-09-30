# smell: No Scaling Before Scaling-sensitive Operation (R22)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/evaluate/test_evaluation.py#L296-L305
# smelly line(s) in the original file: 299
# smelly line(s) in this file: 10
# ids: mlflow_0188
def get_binary_logistic_regressor_model_uri():
    X, y = get_breast_cancer_dataset()
    clf = sklearn.linear_model.LogisticRegression()
    clf.fit(X, y)

    with mlflow.start_run() as run:
        mlflow.sklearn.log_model(clf, "bin_clf_model")
        binary_logistic_regressor_model_uri = get_artifact_uri(run.info.run_id, "bin_clf_model")

    return binary_logistic_regressor_model_uri
