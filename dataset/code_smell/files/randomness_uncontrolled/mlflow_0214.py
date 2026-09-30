# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tracking/fluent/test_fluent.py#L1035-L1040
# smelly line(s) in the original file: 1039
# smelly line(s) in this file: 11
# ids: mlflow_0214
def test_search_runs_by_non_existing_experiment_name():
    """When invalid experiment names are used (including None), it should return an empty
    collection.
    """
    for name in [None, f"Random {random.randint(1, 1e6)}"]:
        assert search_runs(experiment_names=[name], output_format="list") == []
