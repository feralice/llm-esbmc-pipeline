# smell: Missing the Mask of Invalid Value (R7)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/dev/custom_metrics_patch.py#L4-L9
# smelly line(s) in the original file: 8
# smelly line(s) in this file: 11
# ids: mlflow_0072
def weighted_mean_squared_error(eval_df, _builtin_metrics):
    return mean_squared_error(
        eval_df["prediction"],
        eval_df["target"],
        sample_weight=1 / eval_df["prediction"].values,
    )
