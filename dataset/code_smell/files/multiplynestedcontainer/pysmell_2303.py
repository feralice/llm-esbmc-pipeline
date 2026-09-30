# smell: MultiplyNestedContainer
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/special/tests/test_basic.py#L2713-L2722
# smelly line(s) in the original file: 2720
# smelly line(s) in this file: 15
# ids: pysmell_2303
# note: Python 2 era source, kept as found
def test_lqmn_gt1(self):
    """algorithm for real arguments changes at 1.0001
       test against analytical result for m=2, n=1
    """
    x0 = 1.0001
    delta = 0.00002
    for x in (x0-delta, x0+delta):
        lq = special.lqmn(2, 1, x)[0][-1, -1]
        expected = 2/(x*x-1)
        assert_almost_equal(lq, expected)
