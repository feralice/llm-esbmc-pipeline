# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L467-L496
# smelly line(s) in the original file: 491
# smelly line(s) in this file: 31
# ids: mlflow_0249
def test_ingests_delta_successfully(use_relative_path, spark_df, tmp_path):
    dataset_path = tmp_path / "test.delta"
    spark_df.write.format("delta").save(str(dataset_path))
    if use_relative_path:
        dataset_path = os.path.relpath(dataset_path)

    IngestStep.from_recipe_config(
        recipe_config={
            "target_col": "label",
            "steps": {
                "ingest": {
                    "using": "delta",
                    "location": str(dataset_path),
                }
            },
        },
        recipe_root=os.getcwd(),
    ).run(output_directory=tmp_path)

    # Spark DataFrames are not ingested with a consistent row order, as doing so would incur a
    # substantial performance cost. Accordingly, we sort the ingested DataFrame and the original
    # DataFrame on the `id` column and reset the DataFrame index to achieve a consistent ordering
    # before testing their equivalence
    reloaded_df = (
        pd.read_parquet(str(tmp_path / "dataset.parquet"))
        .sort_values(by="id")
        .reset_index(drop=True)
    )
    spark_to_pandas_df = spark_df.toPandas().sort_values(by="id").reset_index(drop=True)
    pd.testing.assert_frame_equal(reloaded_df, spark_to_pandas_df)
