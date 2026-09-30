# smell: No Scaling Before Scaling-sensitive Operation (R22)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/evaluate/test_evaluation.py#L313-L322
# smelly line(s) in the original file: 316
# smelly line(s) in this file: 10
# ids: mlflow_0189
def get_svm_model_url():
    X, y = get_breast_cancer_dataset()
    clf = sklearn.svm.LinearSVC()
    clf.fit(X, y)

    with mlflow.start_run() as run:
        mlflow.sklearn.log_model(clf, "svm_model")
        svm_model_uri = get_artifact_uri(run.info.run_id, "svm_model")

    return svm_model_uri
