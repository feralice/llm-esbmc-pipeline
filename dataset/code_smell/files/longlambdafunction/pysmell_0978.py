# smell: LongLambdaFunction
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/numpy/numpy/blob/v1.9.2/numpy/core/tests/test_datetime.py#L519-L531
# smelly line(s) in the original file: 525
# smelly line(s) in this file: 14
# ids: pysmell_0978
# note: Python 2 era source, kept as found
def test_datetime_array_str(self):
    a = np.array(['2011-03-16', '1920-01-01', '2013-05-19'], dtype='M')
    assert_equal(str(a), "['2011-03-16' '1920-01-01' '2013-05-19']")

    a = np.array(['2011-03-16T13:55Z', '1920-01-01T03:12Z'], dtype='M')
    assert_equal(np.array2string(a, separator=', ',
                formatter={'datetime': lambda x :
                        "'%s'" % np.datetime_as_string(x, timezone='UTC')}),
                 "['2011-03-16T13:55Z', '1920-01-01T03:12Z']")

    # Check that one NaT doesn't corrupt subsequent entries
    a = np.array(['2010', 'NaT', '2030']).astype('M')
    assert_equal(str(a), "['2010' 'NaT' '2030']")
