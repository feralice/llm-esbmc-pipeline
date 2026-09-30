# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L190-L213
# smelly line(s) in the original file: 212
# smelly line(s) in this file: 29
# ids: mlflow_0241
def test_ingests_remote_http_datasets_with_multiple_files_successfully(tmp_path):
    with mock.patch(
        "steps.ingest.load_file_as_dataframe",
        custom_load_wine_csv,
    ):
        IngestStep.from_recipe_config(
            recipe_config={
                "target_col": "density",
                "steps": {
                    "ingest": {
                        "skip_data_profiling": True,
                        "using": "csv",
                        "location": [
                            "https://raw.githubusercontent.com/mlflow/mlflow/master/tests/datasets/winequality-red.csv",
                            "https://raw.githubusercontent.com/mlflow/mlflow/master/tests/datasets/winequality-white.csv",
                        ],
                        "loader_method": "load_file_as_dataframe",
                    }
                },
            },
            recipe_root=os.getcwd(),
        ).run(output_directory=tmp_path)
        reloaded_df = pd.read_parquet(str(tmp_path / "dataset.parquet"))
        assert reloaded_df.count()[0] == 6497
