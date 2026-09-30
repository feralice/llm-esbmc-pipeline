# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/shap/test_log.py#L29-L33
# smelly line(s) in the original file: 32
# smelly line(s) in this file: 10
# ids: mlflow_0262
def shap_model():
    X, y = load_diabetes(return_X_y=True, as_frame=True)
    model = sklearn.ensemble.RandomForestRegressor(n_estimators=100)
    model.fit(X, y)
    return shap.Explainer(model.predict, X, algorithm="permutation")
