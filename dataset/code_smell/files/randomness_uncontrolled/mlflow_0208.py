# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tracking/fluent/test_fluent.py#L264-L270
# smelly line(s) in the original file: 266
# smelly line(s) in this file: 9
# ids: mlflow_0208
def test_get_experiment_id_with_active_experiment_returns_active_experiment_id():
    # Create a new experiment and set that as active experiment
    name = "Random experiment %d" % random.randint(1, 1e6)
    exp_id = mlflow.create_experiment(name)
    assert exp_id is not None
    mlflow.set_experiment(name)
    assert _get_experiment_id() == exp_id
