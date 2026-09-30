# smell: LongLambdaFunction
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/numpy/numpy/blob/v1.9.2/numpy/lib/tests/test_io.py#L1111-L1135
# smelly line(s) in the original file: 1132
# smelly line(s) in this file: 29
# ids: pysmell_0982
# note: Python 2 era source, kept as found
def test_dtype_with_object(self):
    "Test using an explicit dtype with an object"
    from datetime import date
    import time
    data = """ 1; 2001-01-01
               2; 2002-01-31 """
    ndtype = [('idx', int), ('code', np.object)]
    func = lambda s: strptime(s.strip(), "%Y-%m-%d")
    converters = {1: func}
    test = np.genfromtxt(TextIO(data), delimiter=";", dtype=ndtype,
                         converters=converters)
    control = np.array(
        [(1, datetime(2001, 1, 1)), (2, datetime(2002, 1, 31))],
        dtype=ndtype)
    assert_equal(test, control)
    #
    ndtype = [('nest', [('idx', int), ('code', np.object)])]
    try:
        test = np.genfromtxt(TextIO(data), delimiter=";",
                             dtype=ndtype, converters=converters)
    except NotImplementedError:
        pass
    else:
        errmsg = "Nested dtype involving objects should be supported."
        raise AssertionError(errmsg)
