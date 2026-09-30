# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/data/test_numpy_dataset.py#L206-L221
# smelly line(s) in the original file: 209
# smelly line(s) in this file: 10
# ids: mlflow_0280
def test_from_numpy_features_only(tmp_path):
    features = np.array([1, 2, 3])
    path = tmp_path / "temp.csv"
    pd.DataFrame(features).to_csv(path)
    mlflow_features = mlflow.data.from_numpy(features, source=path)

    assert isinstance(mlflow_features, NumpyDataset)
    assert np.array_equal(mlflow_features.features, features)
    assert mlflow_features.schema == TensorDatasetSchema(features=_infer_schema(features))
    assert mlflow_features.profile == {
        "features_shape": features.shape,
        "features_size": features.size,
        "features_nbytes": features.nbytes,
    }

    assert isinstance(mlflow_features.source, FileSystemDatasetSource)
