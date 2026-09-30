# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/gluon/test_gluon_model_export.py#L62-L70
# smelly line(s) in the original file: 65, 66
# smelly line(s) in this file: 10, 11
# ids: mlflow_0227, mlflow_0228
def model_data():
    N = 1_000
    shape = (N, 1, 28, 28)
    labels = np.random.randint(0, 10, size=N)
    train_data = np.random.random(shape)
    train_data = array_module.array(train_data.reshape(-1, 784))
    train_label = array_module.array(labels)
    test_data = array_module.array(train_data.reshape(-1, 784))
    return train_data, train_label, test_data
