# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/mlflow/recipes/cards/__init__.py#L180-L183
# smelly line(s) in the original file: 182
# smelly line(s) in this file: 9
# ids: mlflow_0031
def get_random_id(length=6):
    return "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(length)
    )
