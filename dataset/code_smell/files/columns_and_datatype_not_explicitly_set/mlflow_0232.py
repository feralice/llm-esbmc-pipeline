# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/data/test_http_dataset_source.py#L50-L99
# smelly line(s) in the original file: 56, 64, 75
# smelly line(s) in this file: 13, 21, 32
# ids: mlflow_0232, mlflow_0233, mlflow_0234
def test_source_load(tmp_path):
    source1 = HTTPDatasetSource(
        "https://raw.githubusercontent.com/mlflow/mlflow/master/tests/datasets/winequality-red.csv"
    )

    loaded1 = source1.load()
    parsed1 = pd.read_csv(loaded1, sep=";")
    # Verify that the expected data was downloaded by checking for an expected column and asserting
    # that several rows are present
    assert "fixed acidity" in parsed1.columns
    assert len(parsed1) > 10

    loaded2 = source1.load(dst_path=tmp_path)
    assert loaded2 == str(tmp_path / "winequality-red.csv")
    parsed2 = pd.read_csv(loaded2, sep=";")
    # Verify that the expected data was downloaded by checking for an expected column and asserting
    # that several rows are present
    assert "fixed acidity" in parsed2.columns
    assert len(parsed1) > 10

    source2 = HTTPDatasetSource(
        "https://raw.githubusercontent.com/mlflow/mlflow/master/tests/datasets/winequality-red.csv#foo?query=param"
    )
    loaded3 = source2.load(dst_path=tmp_path)
    assert loaded3 == str(tmp_path / "winequality-red.csv")
    parsed3 = pd.read_csv(loaded3, sep=";")
    assert "fixed acidity" in parsed3.columns
    assert len(parsed1) > 10

    source3 = HTTPDatasetSource("https://github.com/")
    loaded4 = source3.load()
    assert os.path.exists(loaded4)
    assert os.path.basename(loaded4) == "dataset_source"

    source4 = HTTPDatasetSource("https://github.com")
    loaded5 = source4.load()
    assert os.path.exists(loaded5)
    assert os.path.basename(loaded5) == "dataset_source"

    def cloud_storage_http_request_with_fast_fail(*args, **kwargs):
        kwargs["max_retries"] = 1
        kwargs["timeout"] = 5
        return cloud_storage_http_request(*args, **kwargs)

    source5 = HTTPDatasetSource("https://nonexistentwebsitebuiltbythemlflowteam112312.com")
    with mock.patch(
        "mlflow.data.http_dataset_source.cloud_storage_http_request",
        side_effect=cloud_storage_http_request_with_fast_fail,
    ), pytest.raises(Exception, match="Max retries exceeded with url"):
        source5.load()
