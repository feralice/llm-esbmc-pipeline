# smell: No Scaling Before Scaling-sensitive Operation (R22)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/databricks/log_runs.py#L21-L52
# smelly line(s) in the original file: 47, 52
# smelly line(s) in this file: 33, 38
# ids: mlflow_0117, mlflow_0118
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", help="Databricks workspace URL")
    parser.add_argument("--token", help="Databricks personal access token")
    parser.add_argument("--user", help="Databricks username")
    parser.add_argument(
        "--experiment-id",
        default=None,
        help="ID of the experiment to log runs in. If unspecified, a new experiment will be created.",
    )
    args = parser.parse_args()

    os.environ["DATABRICKS_HOST"] = args.host
    os.environ["DATABRICKS_TOKEN"] = args.token

    mlflow.set_tracking_uri("databricks")
    if args.experiment_id:
        experiment = mlflow.set_experiment(experiment_id=args.experiment_id)
    else:
        experiment = mlflow.set_experiment(f"/Users/{args.user}/{uuid.uuid4().hex}")

    print(f"Logging runs in {args.host}#/mlflow/experiments/{experiment.experiment_id}")
    mlflow.sklearn.autolog(max_tuning_runs=None)
    iris = datasets.load_iris()
    parameters = {"kernel": ("linear", "rbf"), "C": [1, 5, 10]}
    clf = GridSearchCV(svm.SVC(), parameters)
    clf.fit(iris.data, iris.target)

    # Log unnested runs
    for params in ParameterGrid(parameters):
        clf = svm.SVC(**params)
        clf.fit(iris.data, iris.target)
