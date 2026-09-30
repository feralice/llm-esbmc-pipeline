# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/rapids/mlflow_project/src/rf_test/train.py#L17-L30
# smelly line(s) in the original file: 26
# smelly line(s) in this file: 16
# ids: mlflow_0385
def load_data(fpath):
    """
    Simple helper function for loading data to be used by CPU/GPU models.

    :param fpath: Path to the data to be ingested
    :return: DataFrame wrapping the data at [fpath]. Data will be in either a Pandas or RAPIDS (cuDF) DataFrame
    """
    import cudf

    df = cudf.read_parquet(fpath)
    X = df.drop(["ArrDelayBinary"], axis=1)
    y = df["ArrDelayBinary"].astype("int32")

    return train_test_split(X, y, test_size=0.2)
