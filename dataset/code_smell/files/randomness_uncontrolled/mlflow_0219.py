# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/gluon/test_gluon_autolog.py#L31-L35
# smelly line(s) in the original file: 33, 34
# smelly line(s) in this file: 9, 10
# ids: mlflow_0219, mlflow_0220
def __getitem__(self, idx):
    return (
        array_module.array(np.random.rand(1, 32)),
        array_module.full(1, random.randint(0, 10), dtype="float32"),
    )
