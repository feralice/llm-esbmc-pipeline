# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L390-L407
# smelly line(s) in the original file: 406, 407
# smelly line(s) in this file: 23, 24
# ids: mlflow_0245, mlflow_0246
def test_ingests_remote_http_datasets_successfully(tmp_path):
    dataset_url = "https://raw.githubusercontent.com/mlflow/mlflow/594a08f2a49c5754bb65d76cd719c15c5b8266e9/examples/sklearn_elasticnet_wine/wine-quality.csv"
    IngestStep.from_recipe_config(
        recipe_config={
            "target_col": "density",
            "steps": {
                "ingest": {
                    "using": "csv",
                    "location": dataset_url,
                    "loader_method": "load_file_as_dataframe",
                }
            },
        },
        recipe_root=os.getcwd(),
    ).run(output_directory=tmp_path)

    reloaded_df = pd.read_parquet(str(tmp_path / "dataset.parquet"))
    pd.testing.assert_frame_equal(reloaded_df, pd.read_csv(dataset_url, index_col=0))
