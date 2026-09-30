# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L141-L182
# smelly line(s) in the original file: 181
# smelly line(s) in this file: 47
# ids: mlflow_0239
def test_ingests_csv_successfully(
    use_relative_path,
    multiple_files,
    explicit_file_list,
    pandas_df,
    tmp_path,
):
    if multiple_files:
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        pandas_df_part1 = pandas_df[:1]
        pandas_df_part2 = pandas_df[1:]
        pandas_df_part1.to_csv(dataset_path / "df1.csv")
        pandas_df_part2.to_csv(dataset_path / "df2.csv")
    else:
        dataset_path = tmp_path / "df.csv"
        pandas_df.to_csv(dataset_path)

    if use_relative_path:
        dataset_path = pathlib.Path(os.path.relpath(dataset_path))

    if explicit_file_list and multiple_files:
        dataset_path = [f'{dataset_path / "df1.csv"}', f'{dataset_path / "df2.csv"}']
    else:
        dataset_path = str(dataset_path)

    IngestStep.from_recipe_config(
        recipe_config={
            "target_col": "C",
            "steps": {
                "ingest": {
                    "using": "csv",
                    "location": dataset_path,
                    "loader_method": "load_file_as_dataframe",
                }
            },
        },
        recipe_root=os.getcwd(),
    ).run(output_directory=tmp_path)

    reloaded_df = pd.read_parquet(str(tmp_path / "dataset.parquet"))
    pd.testing.assert_frame_equal(reloaded_df, pandas_df)
