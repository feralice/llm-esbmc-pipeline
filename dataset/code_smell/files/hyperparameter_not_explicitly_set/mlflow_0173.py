# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pyfunc/test_dependencies_functions.py#L242-L247
# smelly line(s) in the original file: 244
# smelly line(s) in this file: 9
# ids: mlflow_0173
def test_get_model_dependencies_with_model_version_uri():
    with mlflow.start_run():
        mlflow.sklearn.log_model(LinearRegression(), "model", registered_model_name="linear")

    deps = get_model_dependencies("models:/linear/1", format="pip")
    assert f"scikit-learn=={sklearn.__version__}" in Path(deps).read_text()
