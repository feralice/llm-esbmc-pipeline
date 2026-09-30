# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/paddle/train_low_level_api.py#L29-L32
# smelly line(s) in the original file: 32
# smelly line(s) in this file: 10
# ids: mlflow_0394
def __init__(self):
    super().__init__()

    self.fc = Linear(in_features=13, out_features=1)
