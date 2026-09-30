# smell: MultiplyNestedContainer
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/sparse/tests/test_base.py#L3617-L3628
# smelly line(s) in the original file: 3623
# smelly line(s) in this file: 14
# ids: pysmell_2298
# note: Python 2 era source, kept as found
def test_sum_duplicates(self):
    coo = coo_matrix((4,3))
    coo.sum_duplicates()
    coo = coo_matrix(([1,2], ([1,0], [1,0])))
    coo.sum_duplicates()
    assert_array_equal(coo.A, [[2,0],[0,1]])
    coo = coo_matrix(([1,2], ([1,1], [1,1])))
    coo.sum_duplicates()
    assert_array_equal(coo.A, [[0,0],[0,3]])
    assert_array_equal(coo.row, [1])
    assert_array_equal(coo.col, [1])
    assert_array_equal(coo.data, [3])
