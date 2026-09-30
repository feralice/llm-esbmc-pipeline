# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/tracking/fluent/test_fluent.py#L184-L261
# smelly line(s) in the original file: 191, 199, 207, 214, 221, 223, 237, 239, 253, 256
# smelly line(s) in this file: 14, 22, 30, 37, 44, 46, 60, 62, 76, 79
# ids: mlflow_0198, mlflow_0199, mlflow_0200, mlflow_0201, mlflow_0202, mlflow_0203, mlflow_0204, mlflow_0205, mlflow_0206, mlflow_0207
def test_get_experiment_id_from_env(monkeypatch):
    # When no env variables are set
    assert not MLFLOW_EXPERIMENT_NAME.is_defined
    assert not MLFLOW_EXPERIMENT_ID.is_defined
    assert _get_experiment_id_from_env() is None

    # set only ID
    name = "random experiment %d" % random.randint(1, 1e6)
    exp_id = mlflow.create_experiment(name)
    assert exp_id is not None
    monkeypatch.delenv(MLFLOW_EXPERIMENT_NAME.name, raising=False)
    monkeypatch.setenv(MLFLOW_EXPERIMENT_ID.name, exp_id)
    assert _get_experiment_id_from_env() == exp_id

    # set only name
    name = "random experiment %d" % random.randint(1, 1e6)
    exp_id = mlflow.create_experiment(name)
    assert exp_id is not None
    monkeypatch.delenv(MLFLOW_EXPERIMENT_ID.name, raising=False)
    monkeypatch.setenv(MLFLOW_EXPERIMENT_NAME.name, name)
    assert _get_experiment_id_from_env() == exp_id

    # create experiment from env name
    name = "random experiment %d" % random.randint(1, 1e6)
    monkeypatch.delenv(MLFLOW_EXPERIMENT_ID.name, raising=False)
    monkeypatch.setenv(MLFLOW_EXPERIMENT_NAME.name, name)
    assert MlflowClient().get_experiment_by_name(name) is None
    assert _get_experiment_id_from_env() is not None

    # assert experiment creation from encapsulating function
    name = "random experiment %d" % random.randint(1, 1e6)
    monkeypatch.delenv(MLFLOW_EXPERIMENT_ID.name, raising=False)
    monkeypatch.setenv(MLFLOW_EXPERIMENT_NAME.name, name)
    assert MlflowClient().get_experiment_by_name(name) is None
    assert _get_experiment_id() is not None

    # assert raises from conflicting experiment_ids
    name = "random experiment %d" % random.randint(1, 1e6)
    exp_id = mlflow.create_experiment(name)
    random_id = random.randint(100, 1e6)
    assert exp_id != random_id
    monkeypatch.delenv(MLFLOW_EXPERIMENT_NAME.name, raising=False)
    monkeypatch.setenv(MLFLOW_EXPERIMENT_ID.name, random_id)
    with pytest.raises(
        MlflowException,
        match=(
            f"The provided {MLFLOW_EXPERIMENT_ID.name} environment variable value "
            f"`{random_id}` does not exist in the tracking server"
        ),
    ):
        _get_experiment_id_from_env()

    # assert raises from name to id mismatch
    name = "random experiment %d" % random.randint(1, 1e6)
    exp_id = mlflow.create_experiment(name)
    random_id = random.randint(100, 1e6)
    assert exp_id != random_id
    monkeypatch.setenvs({MLFLOW_EXPERIMENT_ID.name: random_id, MLFLOW_EXPERIMENT_NAME.name: name})
    with pytest.raises(
        MlflowException,
        match=(
            f"The provided {MLFLOW_EXPERIMENT_ID.name} environment variable value "
            f"`{random_id}` does not match the experiment id"
        ),
    ):
        _get_experiment_id_from_env()

    # assert does not raise if active experiment is set with invalid env variables
    invalid_name = "invalid experiment"
    name = "random experiment %d" % random.randint(1, 1e6)
    exp_id = mlflow.create_experiment(name)
    assert exp_id is not None
    random_id = random.randint(100, 1e6)
    monkeypatch.setenvs(
        {MLFLOW_EXPERIMENT_ID.name: random_id, MLFLOW_EXPERIMENT_NAME.name: invalid_name}
    )
    mlflow.set_experiment(experiment_id=exp_id)
    assert _get_experiment_id() == exp_id
