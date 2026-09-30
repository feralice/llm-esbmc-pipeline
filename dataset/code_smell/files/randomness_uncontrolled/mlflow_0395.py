# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/paddle/train_low_level_api.py#L45-L45
# smelly line(s) in the original file: 45
# smelly line(s) in this file: 7
# ids: mlflow_0395
opt = paddle.optimizer.SGD(learning_rate=0.01, parameters=model.parameters())
