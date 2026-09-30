# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_split_step.py#L86-L108
# smelly line(s) in the original file: 99, 100, 101
# smelly line(s) in this file: 20, 21, 22
# ids: mlflow_0322, mlflow_0323, mlflow_0324
def test_split_step_run_with_multiple_classes(tmp_path, monkeypatch):
    num_good_rows, split_output_dir, _ = set_up_dataset(tmp_path, num_classes=10)

    split_ratios = [0.6, 0.3, 0.1]

    monkeypatch.setenv(_MLFLOW_RECIPES_EXECUTION_DIRECTORY_ENV_VAR, str(tmp_path))
    with mock.patch("mlflow.recipes.step.get_recipe_name", return_value="fake_name"):
        split_step = SplitStep(
            {"split_ratios": split_ratios, "target_col": "y", "recipe": "classification/v1"},
            "fake_root",
        )
        split_step.run(str(split_output_dir))

    output_train_df = pd.read_parquet(str(split_output_dir / "train.parquet"))
    output_validation_df = pd.read_parquet(str(split_output_dir / "validation.parquet"))
    output_test_df = pd.read_parquet(str(split_output_dir / "test.parquet"))

    assert len(output_train_df) + len(output_validation_df) + len(output_test_df) == num_good_rows

    merged_output_df = pd.concat([output_train_df, output_validation_df, output_test_df])
    assert merged_output_df.columns.tolist() == ["a", "b", "y"]
    assert set(merged_output_df.a.tolist()) == set(range(num_good_rows))
    assert set(merged_output_df.b.tolist()) == {str(i) for i in range(num_good_rows)}
