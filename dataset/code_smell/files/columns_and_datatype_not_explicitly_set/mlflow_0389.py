# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/prophet/train.py#L20-L20
# smelly line(s) in the original file: 20
# smelly line(s) in this file: 7
# ids: mlflow_0389
sales_data = pd.read_csv(SOURCE_DATA)
