# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tracking/fluent/test_fluent.py#L1017-L1032
# smelly line(s) in the original file: 1018
# smelly line(s) in this file: 8
# ids: mlflow_0213
def test_search_runs_by_experiment_name():
    name = f"Random experiment {random.randint(1, 1e6)}"
    exp_id = uuid.uuid4().hex
    experiment = create_experiment(experiment_id=exp_id, name=name)
    runs, data = create_test_runs_and_expected_data(exp_id)

    get_experiment_patch = mock.patch(
        "mlflow.tracking.fluent.get_experiment_by_name", return_value=experiment
    )
    get_paginated_runs_patch = mock.patch(
        "mlflow.tracking.fluent.get_results_from_paginated_fn", return_value=runs
    )

    with get_experiment_patch, get_paginated_runs_patch:
        result = search_runs(experiment_names=[name])
        validate_search_runs(result, data, "pandas")
