# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pyfunc/test_pyfunc_schema_enforcement.py#L42-L233
# smelly line(s) in the original file: 179, 186
# smelly line(s) in this file: 144, 151
# ids: mlflow_0289, mlflow_0290
def test_column_schema_enforcement():
    m = Model()
    input_schema = Schema(
        [
            ColSpec("integer", "a"),
            ColSpec("long", "b"),
            ColSpec("float", "c"),
            ColSpec("double", "d"),
            ColSpec("boolean", "e"),
            ColSpec("string", "g"),
            ColSpec("binary", "f"),
            ColSpec("datetime", "h"),
        ]
    )
    m.signature = ModelSignature(inputs=input_schema)
    pyfunc_model = PyFuncModel(model_meta=m, model_impl=TestModel())
    pdf = pd.DataFrame(
        data=[[1, 2, 3, 4, True, "x", bytes([1]), "2021-01-01 00:00:00.1234567"]],
        columns=["b", "d", "a", "c", "e", "g", "f", "h"],
        dtype=object,
    )
    pdf["a"] = pdf["a"].astype(np.int32)
    pdf["b"] = pdf["b"].astype(np.int64)
    pdf["c"] = pdf["c"].astype(np.float32)
    pdf["d"] = pdf["d"].astype(np.float64)
    pdf["h"] = pdf["h"].astype(np.dtype("datetime64[ns]"))
    # test that missing column raises
    match_missing_inputs = "Model is missing inputs"
    with pytest.raises(MlflowException, match=match_missing_inputs):
        res = pyfunc_model.predict(pdf[["b", "d", "a", "e", "g", "f", "h"]])

    # test that extra column is ignored
    pdf["x"] = 1

    # test that columns are reordered, extra column is ignored
    res = pyfunc_model.predict(pdf)
    assert all((res == pdf[input_schema.input_names()]).all())

    expected_types = dict(zip(input_schema.input_names(), input_schema.pandas_types()))
    # MLflow datetime type in input_schema does not encode precision, so add it for assertions
    expected_types["h"] = np.dtype("datetime64[ns]")
    # object cannot be converted to pandas Strings at the moment
    expected_types["f"] = object
    expected_types["g"] = object
    actual_types = res.dtypes.to_dict()
    assert expected_types == actual_types

    # Test conversions
    # 1. long -> integer raises
    pdf["a"] = pdf["a"].astype(np.int64)
    match_incompatible_inputs = "Incompatible input types"
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["a"] = pdf["a"].astype(np.int32)
    # 2. integer -> long works
    pdf["b"] = pdf["b"].astype(np.int32)
    res = pyfunc_model.predict(pdf)
    assert all((res == pdf[input_schema.input_names()]).all())
    assert res.dtypes.to_dict() == expected_types
    pdf["b"] = pdf["b"].astype(np.int64)

    # 3. unsigned int -> long works
    pdf["b"] = pdf["b"].astype(np.uint32)
    res = pyfunc_model.predict(pdf)
    assert all((res == pdf[input_schema.input_names()]).all())
    assert res.dtypes.to_dict() == expected_types
    pdf["b"] = pdf["b"].astype(np.int64)

    # 4. unsigned int -> int raises
    pdf["a"] = pdf["a"].astype(np.uint32)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["a"] = pdf["a"].astype(np.int32)

    # 5. double -> float raises
    pdf["c"] = pdf["c"].astype(np.float64)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["c"] = pdf["c"].astype(np.float32)

    # 6. float -> double works, double -> float does not
    pdf["d"] = pdf["d"].astype(np.float32)
    res = pyfunc_model.predict(pdf)
    assert res.dtypes.to_dict() == expected_types
    pdf["d"] = pdf["d"].astype(np.float64)
    pdf["c"] = pdf["c"].astype(np.float64)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["c"] = pdf["c"].astype(np.float32)

    # 7. int -> float raises
    pdf["c"] = pdf["c"].astype(np.int32)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["c"] = pdf["c"].astype(np.float32)

    # 8. int -> double works
    pdf["d"] = pdf["d"].astype(np.int32)
    pyfunc_model.predict(pdf)
    assert all((res == pdf[input_schema.input_names()]).all())
    assert res.dtypes.to_dict() == expected_types

    # 9. long -> double raises
    pdf["d"] = pdf["d"].astype(np.int64)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["d"] = pdf["d"].astype(np.float64)

    # 10. any float -> any int raises
    pdf["a"] = pdf["a"].astype(np.float32)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    # 10. any float -> any int raises
    pdf["a"] = pdf["a"].astype(np.float64)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["a"] = pdf["a"].astype(np.int32)
    pdf["b"] = pdf["b"].astype(np.float64)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["b"] = pdf["b"].astype(np.int64)

    pdf["b"] = pdf["b"].astype(np.float64)
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(pdf)
    pdf["b"] = pdf["b"].astype(np.int64)

    # 11. objects work
    pdf["b"] = pdf["b"].astype(object)
    pdf["d"] = pdf["d"].astype(object)
    pdf["e"] = pdf["e"].astype(object)
    pdf["f"] = pdf["f"].astype(object)
    pdf["g"] = pdf["g"].astype(object)
    res = pyfunc_model.predict(pdf)
    assert res.dtypes.to_dict() == expected_types

    # 12. datetime64[D] (date only) -> datetime64[x] works
    pdf["h"] = pdf["h"].values.astype("datetime64[D]")
    res = pyfunc_model.predict(pdf)
    assert res.dtypes.to_dict() == expected_types
    pdf["h"] = pdf["h"].astype("datetime64[s]")

    # 13. np.ndarrays can be converted to dataframe but have no columns
    with pytest.raises(MlflowException, match=match_missing_inputs):
        pyfunc_model.predict(pdf.values)

    # 14. dictionaries of str -> list/nparray work
    arr = np.array([1, 2, 3])
    d = {
        "a": arr.astype("int32"),
        "b": arr.astype("int64"),
        "c": arr.astype("float32"),
        "d": arr.astype("float64"),
        "e": [True, False, True],
        "g": ["a", "b", "c"],
        "f": [bytes(0), bytes(1), bytes(1)],
        "h": np.array(["2020-01-01", "2020-02-02", "2020-03-03"], dtype=np.datetime64),
    }
    res = pyfunc_model.predict(d)
    assert res.dtypes.to_dict() == expected_types

    # 15. dictionaries of str -> list[list] fail
    d = {
        "a": [arr.astype("int32")],
        "b": [arr.astype("int64")],
        "c": [arr.astype("float32")],
        "d": [arr.astype("float64")],
        "e": [[True, False, True]],
        "g": [["a", "b", "c"]],
        "f": [[bytes(0), bytes(1), bytes(1)]],
        "h": [np.array(["2020-01-01", "2020-02-02", "2020-03-03"], dtype=np.datetime64)],
    }
    with pytest.raises(MlflowException, match=match_incompatible_inputs):
        pyfunc_model.predict(d)

    # 16. conversion to dataframe fails
    d = {
        "a": [1],
        "b": [1, 2],
        "c": [1, 2, 3],
    }
    with pytest.raises(
        MlflowException,
        match="This model contains a column-based signature, which suggests a DataFrame input.",
    ):
        pyfunc_model.predict(d)

    # 17. conversion from Decimal to float is allowed since numpy currently has no support for the
    #  data type.
    pdf["d"] = [decimal.Decimal(1.0)]
    res = pyfunc_model.predict(pdf)
    assert res.dtypes.to_dict() == expected_types
