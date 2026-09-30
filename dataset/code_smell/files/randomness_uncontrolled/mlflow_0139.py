# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/pyspark_ml_autologging/pipeline.py#L14-L14
# smelly line(s) in the original file: 14
# smelly line(s) in this file: 7
# ids: mlflow_0139
train, test = df.randomSplit([0.8, 0.2])
