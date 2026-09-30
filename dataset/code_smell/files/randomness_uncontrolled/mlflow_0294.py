# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pytorch/test_pytorch_metric_value_conversion_utils.py#L12-L18
# smelly line(s) in the original file: 13
# smelly line(s) in this file: 8
# ids: mlflow_0294
def test_reraised_value_errors():
    multi_item_torch_tensor = torch.rand((2, 2))

    with pytest.raises(MlflowException, match=r"Failed to convert metric value to float") as e:
        convert_metric_value_to_float_if_possible(multi_item_torch_tensor)

    assert e.value.error_code == ErrorCode.Name(INVALID_PARAMETER_VALUE)
