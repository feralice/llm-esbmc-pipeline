# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L367-L386
# smelly line(s) in the original file: 385
# smelly line(s) in this file: 25
# ids: mlflow_0244
def test_ingests_remote_s3_datasets_successfully(mock_s3_bucket, pandas_df, tmp_path):
    dataset_path = tmp_path / "df.parquet"
    pandas_df.to_parquet(dataset_path)
    S3ArtifactRepository(f"s3://{mock_s3_bucket}").log_artifact(str(dataset_path))

    IngestStep.from_recipe_config(
        recipe_config={
            "target_col": "C",
            "steps": {
                "ingest": {
                    "using": "parquet",
                    "location": f"s3://{mock_s3_bucket}/df.parquet",
                }
            },
        },
        recipe_root=os.getcwd(),
    ).run(output_directory=tmp_path)

    reloaded_df = pd.read_parquet(str(tmp_path / "dataset.parquet"))
    pd.testing.assert_frame_equal(reloaded_df, pandas_df)
