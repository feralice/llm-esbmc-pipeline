# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L411-L437
# smelly line(s) in the original file: 432
# smelly line(s) in this file: 28
# ids: mlflow_0247
def test_ingests_spark_sql_successfully(spark_df, tmp_path):
    spark_df.write.mode("overwrite").saveAsTable("test_table")

    IngestStep.from_recipe_config(
        recipe_config={
            "target_col": "label",
            "steps": {
                "ingest": {
                    "using": "spark_sql",
                    "sql": "SELECT * FROM test_table ORDER BY id",
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
