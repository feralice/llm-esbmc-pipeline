# smell: Hyperparameter Not Explicitly Set (R5)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/ray_serve/train_model.py#L23-L23
# smelly line(s) in the original file: 23
# smelly line(s) in this file: 7
# ids: mlflow_0398
model = GradientBoostingClassifier()
