# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pytorch/test_pytorch_metric_value_conversion_utils.py#L26-L34
# smelly line(s) in the original file: 27
# smelly line(s) in this file: 8
# ids: mlflow_0296
def test_log_torch_tensor_as_metric():
    torch_tensor_val = torch.rand(1)
    torch_tensor_float_val = float(torch_tensor_val[0])

    with start_run() as run:
        mlflow.log_metric("name_torch", torch_tensor_val)

    finished_run = tracking.MlflowClient().get_run(run.info.run_id)
    assert finished_run.data.metrics == {"name_torch": torch_tensor_float_val}
