# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/recipes/test_ingest_step.py#L862-L911
# smelly line(s) in the original file: 905
# smelly line(s) in this file: 50
# ids: mlflow_0253
def test_ingests_spark_sql_datetime_successfully(spark_session, tmp_path):
    from pyspark.sql.functions import (
        col,
        rand,
        unix_timestamp,
        to_timestamp,
        current_date,
        current_timestamp,
    )

    spark = spark_session.builder.getOrCreate()
    spark_df = (
        spark.range(10)
        .withColumn("f1", rand(seed=123))
        .withColumn("date_today", current_date())
        .withColumn("time_now", current_timestamp())
        .withColumn(
            "timestamp", to_timestamp(unix_timestamp("time_now") - col("f1") * 60 * 60 * 24)
        )
        .drop("time_now")
    )
    # data = [("2019-01-23", 1), ("2019-06-24", 2), ("2019-09-20", 3)]
    # spark_df = spark_session.createDataFrame(data).toDF("date", "increment")
    spark_df.write.mode("overwrite").saveAsTable("test_table")

    IngestStep.from_recipe_config(
        recipe_config={
            "target_col": "f1",
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

    assert reloaded_df["date_today"].dtype == "datetime64[ns]"
    assert reloaded_df["timestamp"].dtype == "datetime64[ns]"
