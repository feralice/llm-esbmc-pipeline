# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tracking/fluent/test_fluent.py#L318-L323
# smelly line(s) in the original file: 319
# smelly line(s) in this file: 8
# ids: mlflow_0211
def test_get_experiment_by_id():
    name = "Random experiment %d" % random.randint(1, 1e6)
    exp_id = mlflow.create_experiment(name)

    experiment = mlflow.get_experiment(exp_id)
    assert experiment.experiment_id == exp_id
