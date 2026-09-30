# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/spacy/train.py#L38-L38
# smelly line(s) in the original file: 38
# smelly line(s) in this file: 7
# ids: mlflow_0399
random.shuffle(TRAIN_DATA)
