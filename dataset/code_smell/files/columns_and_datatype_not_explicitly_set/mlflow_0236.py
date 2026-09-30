# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L65-L94
# smelly line(s) in the original file: 93
# smelly line(s) in this file: 35
# ids: mlflow_0236
def test_ingests_parquet_successfully(use_relative_path, multiple_files, pandas_df, tmp_path):
    if multiple_files:
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        pandas_df_part1 = pandas_df[:1]
        pandas_df_part2 = pandas_df[1:]
        pandas_df_part1.to_parquet(dataset_path / "df1.parquet")
        pandas_df_part2.to_parquet(dataset_path / "df2.parquet")
    else:
        dataset_path = tmp_path / "df.parquet"
        pandas_df.to_parquet(dataset_path)

    if use_relative_path:
        dataset_path = os.path.relpath(dataset_path)

    IngestStep.from_recipe_config(
        recipe_config={
            "target_col": "C",
            "steps": {
                "ingest": {
                    "using": "parquet",
                    "location": str(dataset_path),
                }
            },
        },
        recipe_root=os.getcwd(),
    ).run(output_directory=tmp_path)

    reloaded_df = pd.read_parquet(str(tmp_path / "dataset.parquet"))
    pd.testing.assert_frame_equal(reloaded_df, pandas_df)
