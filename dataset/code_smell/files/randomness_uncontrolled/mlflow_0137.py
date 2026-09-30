# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/pyspark_ml_autologging/one_vs_rest.py#L12-L12
# smelly line(s) in the original file: 12
# smelly line(s) in this file: 7
# ids: mlflow_0137
train, test = df.randomSplit([0.8, 0.2])
