# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/prophet/test_prophet_model_export.py#L121-L125
# smelly line(s) in the original file: 124
# smelly line(s) in this file: 10
# ids: mlflow_0285
def prophet_model():
    np.random.seed(SEED)
    data = DataGeneration(**TEST_CONFIG).create_series_df()
    model = Prophet().fit(data)
    return ModelWithSource(model, data)
