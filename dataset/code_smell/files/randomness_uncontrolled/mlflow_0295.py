# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pytorch/test_pytorch_metric_value_conversion_utils.py#L21-L23
# smelly line(s) in the original file: 22
# smelly line(s) in this file: 8
# ids: mlflow_0295
def test_convert_metric_value_to_float():
    torch_tensor_val = torch.rand(1)
    assert convert_metric_value_to_float_if_possible(torch_tensor_val) == float(torch_tensor_val[0])
