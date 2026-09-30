# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/evaluate/test_evaluation.py#L255-L264
# smelly line(s) in the original file: 258
# smelly line(s) in this file: 10
# ids: mlflow_0177
def get_spark_linear_regressor_model_uri():
    spark_df = get_diabetes_spark_dataset()
    reg = SparkLinearRegression()
    spark_reg_model = reg.fit(spark_df)

    with mlflow.start_run() as run:
        mlflow.spark.log_model(spark_reg_model, "spark_reg_model")
        spark_linear_regressor_model_uri = get_artifact_uri(run.info.run_id, "spark_reg_model")

    return spark_linear_regressor_model_uri
