# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/paddle/train_low_level_api.py#L51-L51
# smelly line(s) in the original file: 51
# smelly line(s) in this file: 7
# ids: mlflow_0396
np.random.shuffle(training_data)
