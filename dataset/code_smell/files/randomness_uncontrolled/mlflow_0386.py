# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/examples/xgboost/xgboost_sklearn/train.py#L14-L33
# smelly line(s) in the original file: 17, 23
# smelly line(s) in this file: 10, 16
# ids: mlflow_0386, mlflow_0387
def main():
    # prepare example dataset
    X, y = load_diabetes(return_X_y=True, as_frame=True)
    X_train, X_test, y_train, y_test = train_test_split(X, y)

    # enable auto logging
    # this includes xgboost.sklearn estimators
    mlflow.xgboost.autolog()

    regressor = xgb.XGBRegressor(n_estimators=20, reg_lambda=1, gamma=0, max_depth=3)
    regressor.fit(X_train, y_train, eval_set=[(X_test, y_test)])
    y_pred = regressor.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    run_id = mlflow.last_active_run().info.run_id
    print("Logged data and model in run {}".format(run_id))

    # show logged data
    for key, data in fetch_logged_data(run_id).items():
        print("\n---------- logged {} ----------".format(key))
        pprint(data)
