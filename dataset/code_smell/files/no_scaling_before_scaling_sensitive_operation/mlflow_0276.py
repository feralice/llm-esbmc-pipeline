# smell: No Scaling Before Scaling-sensitive Operation (R22)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/utils/test_model_utils.py#L18-L24
# smelly line(s) in the original file: 23
# smelly line(s) in this file: 12
# ids: mlflow_0276
def sklearn_knn_model():
    iris = datasets.load_iris()
    X = iris.data[:, :2]  # we only take the first two features.
    y = iris.target
    knn_model = knn.KNeighborsClassifier()
    knn_model.fit(X, y)
    return knn_model
