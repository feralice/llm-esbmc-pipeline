# smell: Data Leakage (R11)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/evaluate/test_evaluation.py#L193-L230
# smelly line(s) in the original file: 226
# smelly line(s) in this file: 40
# ids: mlflow_0175
def get_pipeline_model_uri():
    """
    Create a pipeline model that transforms and trains on the dataset returned by
    `get_pipeline_model_dataset`. The pipeline model imputes the missing values in
    input dataset, encodes categorical features, and then trains a logistic regression
    model.
    """
    data, target_col = get_pipeline_model_dataset()
    X = data.drop(target_col, axis=1)
    y = data[target_col].to_numpy()

    encoder = sklearn.preprocessing.OrdinalEncoder()
    str_imputer = sklearn.impute.SimpleImputer(missing_values=None, strategy="most_frequent")
    num_imputer = sklearn.impute.SimpleImputer(missing_values=np.nan, strategy="mean")
    preproc_pipeline = sklearn.pipeline.Pipeline(
        [
            ("imputer", str_imputer),
            ("encoder", encoder),
        ]
    )

    pipeline = sklearn.pipeline.Pipeline(
        [
            (
                "transformer",
                sklearn.compose.make_column_transformer(
                    (preproc_pipeline, ["f1", "f2"]),
                    (num_imputer, ["f3", "f4"]),
                ),
            ),
            ("clf", sklearn.linear_model.LogisticRegression()),
        ]
    )
    pipeline.fit(X, y)

    with mlflow.start_run():
        model_info = mlflow.sklearn.log_model(pipeline, "pipeline_model")
        return model_info.model_uri
