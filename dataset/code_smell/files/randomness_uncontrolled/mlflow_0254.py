# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/lightgbm/test_lightgbm_autolog.py#L457-L481
# smelly line(s) in the original file: 463, 464, 465
# smelly line(s) in this file: 13, 14, 15
# ids: mlflow_0254, mlflow_0255, mlflow_0256
def ranking_dataset(num_rows=100, num_queries=10):
    # https://stackoverflow.com/a/67621253
    num_rows_per_query = num_rows // num_queries
    df = pd.DataFrame(
        {
            "query_id": [i for i in range(num_queries) for _ in range(num_rows_per_query)],
            "f1": np.random.random(size=(num_rows,)),
            "f2": np.random.random(size=(num_rows,)),
            "relevance": np.random.randint(2, size=(num_rows,)),
        }
    )
    train_size = int(num_rows * 0.75)
    df_train = df[:train_size]
    df_valid = df[train_size:]
    # Train
    group_train = df_train.groupby("query_id")["query_id"].count().to_numpy()
    X_train = df_train.drop(["query_id", "relevance"], axis=1)
    y_train = df_train["relevance"]
    train_set = lgb.Dataset(X_train, y_train, group=group_train)
    # Validation
    group_val = df_valid.groupby("query_id")["query_id"].count().to_numpy()
    X_valid = df_valid.drop(["query_id", "relevance"], axis=1)
    y_valid = df_valid["relevance"]
    valid_set = lgb.Dataset(X_valid, y_valid, group=group_val)
    return train_set, valid_set
