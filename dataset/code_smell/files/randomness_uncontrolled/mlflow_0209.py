# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tracking/fluent/test_fluent.py#L287-L298
# smelly line(s) in the original file: 288
# smelly line(s) in this file: 8
# ids: mlflow_0209
def test_get_experiment_id_in_databricks_with_active_experiment_returns_active_experiment_id():
    exp_name = "random experiment %d" % random.randint(1, 1e6)
    exp_id = mlflow.create_experiment(exp_name)
    mlflow.set_experiment(exp_name)
    notebook_id = str(int(exp_id) + 73)

    with mock.patch(
        "mlflow.tracking.fluent.default_experiment_registry.get_experiment_id",
        return_value=notebook_id,
    ):
        assert _get_experiment_id() != notebook_id
        assert _get_experiment_id() == exp_id
