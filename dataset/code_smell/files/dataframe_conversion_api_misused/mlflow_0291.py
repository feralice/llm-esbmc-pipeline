# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pyfunc/test_pyfunc_schema_enforcement.py#L559-L597
# smelly line(s) in the original file: 576
# smelly line(s) in this file: 24
# ids: mlflow_0291
def test_column_schema_enforcement_no_col_names():
    m = Model()
    input_schema = Schema([ColSpec("double"), ColSpec("double"), ColSpec("double")])
    m.signature = ModelSignature(inputs=input_schema)
    pyfunc_model = PyFuncModel(model_meta=m, model_impl=TestModel())
    test_data = [[1.0, 2.0, 3.0]]

    # Can call with just a list
    pd.testing.assert_frame_equal(pyfunc_model.predict(test_data), pd.DataFrame(test_data))

    # Or can call with a DataFrame without column names
    pd.testing.assert_frame_equal(
        pyfunc_model.predict(pd.DataFrame(test_data)), pd.DataFrame(test_data)
    )

    # # Or can call with a np.ndarray
    pd.testing.assert_frame_equal(
        pyfunc_model.predict(pd.DataFrame(test_data).values), pd.DataFrame(test_data)
    )

    # Or with column names!
    pdf = pd.DataFrame(data=test_data, columns=["a", "b", "c"])
    pd.testing.assert_frame_equal(pyfunc_model.predict(pdf), pdf)

    # Must provide the right number of arguments
    with pytest.raises(MlflowException, match="the provided value only has 2 inputs."):
        pyfunc_model.predict([[1.0, 2.0]])

    # Must provide the right types
    with pytest.raises(MlflowException, match="Can not safely convert int64 to float64"):
        pyfunc_model.predict([[1, 2, 3]])

    # Can only provide data type that can be converted to dataframe...
    with pytest.raises(MlflowException, match="Expected input to be DataFrame or list. Found: set"):
        pyfunc_model.predict({1, 2, 3})

    # 9. dictionaries of str -> list/nparray work
    d = {"a": [1.0], "b": [2.0], "c": [3.0]}
    pd.testing.assert_frame_equal(pyfunc_model.predict(d), pd.DataFrame(d))
