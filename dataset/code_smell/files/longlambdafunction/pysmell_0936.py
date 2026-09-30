# smell: LongLambdaFunction
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/special/tests/test_mpmath.py#L1226-L1235
# smelly line(s) in the original file: 1233
# smelly line(s) in this file: 15
# ids: pysmell_0936
# note: Python 2 era source, kept as found
def test_hyp2f0(self):
    def hyp2f0(a, b, x):
        v, err = sc.hyp2f0(a, b, x, 1)
        if abs(err) > max(1, abs(v)) * 1e-7:
            return np.nan
        return v
    assert_mpmath_equal(hyp2f0,
                        lambda a, b, x: _time_limited(0.1)(_exception_to_nan(_trace_args(mpmath.hyp2f0)))(
                            a, b, x, **HYPERKW),
                        [Arg(), Arg(), Arg()])
