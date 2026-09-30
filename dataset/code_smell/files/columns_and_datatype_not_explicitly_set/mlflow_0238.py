# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L101-L134
# smelly line(s) in the original file: 133
# smelly line(s) in this file: 39
# ids: mlflow_0238
def test_ingests_custom_format(pandas_df, tmp_recipe_root_path, tmp_path):
    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()
    pandas_df_part1 = pandas_df[:1]
    pandas_df_part2 = pandas_df[1:]
    pandas_df_part1.to_csv(dataset_path / "df1.csv")
    pandas_df_part2.to_csv(dataset_path / "df2.csv")
    dataset_path = [f'{dataset_path / "df1.csv"}', f'{dataset_path / "df2.csv"}']

    recipe_yaml = tmp_recipe_root_path.joinpath(_RECIPE_CONFIG_FILE_NAME)
    recipe_yaml.write_text(
        f"""
        recipe: "regression/v1"
        target_col: "C"
        steps:
            ingest:
                skip_data_profiling: True
                using: custom
                location: {dataset_path}
                loader_method: load_file_as_dataframe
        """
    )
    recipe_steps_dir = tmp_recipe_root_path.joinpath("steps")
    recipe_steps_dir.mkdir(parents=True)

    m_ingest = Mock()
    m_ingest.load_file_as_dataframe = custom_load_csv
    with mock.patch.dict("sys.modules", {"steps.ingest": m_ingest}):
        recipe_config = read_yaml(tmp_recipe_root_path, _RECIPE_CONFIG_FILE_NAME)
        ingest_step = IngestStep.from_recipe_config(recipe_config, str(tmp_recipe_root_path))
        ingest_step.run(output_directory=tmp_path)

        reloaded_df = pd.read_parquet(str(tmp_path / "dataset.parquet"))
        pd.testing.assert_frame_equal(reloaded_df, pandas_df)
