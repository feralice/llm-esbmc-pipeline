# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/evaluation/evaluate_with_custom_metrics_comprehensive.py#L22-L22
# smelly line(s) in the original file: 22
# smelly line(s) in this file: 7
# ids: mlflow_0094
lin_reg = LinearRegression().fit(X_train, y_train)
