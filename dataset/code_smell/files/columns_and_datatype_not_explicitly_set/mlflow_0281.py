# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/data/test_numpy_dataset.py#L224-L246
# smelly line(s) in the original file: 228
# smelly line(s) in this file: 11
# ids: mlflow_0281
def test_from_numpy_features_and_targets(tmp_path):
    features = np.array([[1, 2, 3], [3, 2, 1], [2, 3, 1]])
    targets = np.array([4, 5, 6])
    path = tmp_path / "temp.csv"
    pd.DataFrame(features).to_csv(path)
    mlflow_ds = mlflow.data.from_numpy(features, targets=targets, source=path)

    assert isinstance(mlflow_ds, NumpyDataset)
    assert np.array_equal(mlflow_ds.features, features)
    assert np.array_equal(mlflow_ds.targets, targets)
    assert mlflow_ds.schema == TensorDatasetSchema(
        features=_infer_schema(features), targets=_infer_schema(targets)
    )
    assert mlflow_ds.profile == {
        "features_shape": features.shape,
        "features_size": features.size,
        "features_nbytes": features.nbytes,
        "targets_shape": targets.shape,
        "targets_size": targets.size,
        "targets_nbytes": targets.nbytes,
    }

    assert isinstance(mlflow_ds.source, FileSystemDatasetSource)
