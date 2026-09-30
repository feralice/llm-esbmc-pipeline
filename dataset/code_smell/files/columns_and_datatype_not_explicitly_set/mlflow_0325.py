# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_split_step.py#L254-L305
# smelly line(s) in the original file: 300, 301, 302
# smelly line(s) in this file: 53, 54, 55
# ids: mlflow_0325, mlflow_0326, mlflow_0327
def test_custom_split_method(tmp_recipe_root_path: Path, tmp_recipe_exec_path: Path):
    ingest_output_dir = tmp_recipe_exec_path / "steps" / "ingest" / "outputs"
    ingest_output_dir.mkdir(parents=True)
    split_output_dir = tmp_recipe_exec_path / "steps" / "split" / "outputs"
    split_output_dir.mkdir(parents=True)
    recipe_steps_dir = tmp_recipe_root_path.joinpath("steps")
    recipe_steps_dir.mkdir(parents=True)

    num_rows = 1000
    input_dataframe = pd.DataFrame(
        {
            "a": list(range(num_rows)),
            "y": [float(i % 2) for i in range(num_rows)],
        }
    )
    input_dataframe.to_parquet(str(ingest_output_dir / "dataset.parquet"))

    recipe_yaml = tmp_recipe_root_path.joinpath(_RECIPE_CONFIG_FILE_NAME)
    recipe_yaml.write_text(
        """
        recipe: "regression/v1"
        target_col: "y"
        primary_metric: "f1_score"
        profile: "test_profile"
        run_args:
            step: "split"
        experiment:
            name: "demo"
            tracking_uri: {tracking_uri}
        steps:
            split:
                using: custom
                split_method: split_method
        """.format(
            tracking_uri=mlflow.get_tracking_uri()
        )
    )

    m_split = Mock()
    m_split.split_method = custom_split

    recipe_config = read_yaml(tmp_recipe_root_path, _RECIPE_CONFIG_FILE_NAME)
    split_step = SplitStep.from_recipe_config(recipe_config, str(tmp_recipe_root_path))
    with mock.patch.dict("sys.modules", {"steps.split": m_split}):
        split_step.run(str(split_output_dir))

    train_dataframe = pd.read_parquet(split_output_dir / _OUTPUT_TRAIN_FILE_NAME)
    validation_dataframe = pd.read_parquet(split_output_dir / _OUTPUT_VALIDATION_FILE_NAME)
    test_dataframe = pd.read_parquet(split_output_dir / _OUTPUT_TEST_FILE_NAME)
    assert len(train_dataframe.index) == 500
    assert len(validation_dataframe.index) == 300
    assert len(test_dataframe.index) == 200
