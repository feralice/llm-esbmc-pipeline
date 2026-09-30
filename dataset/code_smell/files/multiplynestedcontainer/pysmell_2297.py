# smell: MultiplyNestedContainer
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/sparse/tests/test_base.py#L2299-L2364
# smelly line(s) in the original file: 2353
# smelly line(s) in this file: 62
# ids: pysmell_2297
# note: Python 2 era source, kept as found
def test_fancy_indexing(self):
    B = asmatrix(arange(50).reshape(5,10))
    A = self.spmatrix(B)

    # [i]
    assert_equal(A[[1,3]].todense(), B[[1,3]])

    # [i,[1,2]]
    assert_equal(A[3,[1,3]].todense(), B[3,[1,3]])
    assert_equal(A[-1,[2,-5]].todense(),B[-1,[2,-5]])
    assert_equal(A[array(-1),[2,-5]].todense(),B[-1,[2,-5]])
    assert_equal(A[-1,array([2,-5])].todense(),B[-1,[2,-5]])
    assert_equal(A[array(-1),array([2,-5])].todense(),B[-1,[2,-5]])

    # [1:2,[1,2]]
    assert_equal(A[:,[2,8,3,-1]].todense(),B[:,[2,8,3,-1]])
    assert_equal(A[3:4,[9]].todense(), B[3:4,[9]])
    assert_equal(A[1:4,[-1,-5]].todense(), B[1:4,[-1,-5]])
    assert_equal(A[1:4,array([-1,-5])].todense(), B[1:4,[-1,-5]])

    # [[1,2],j]
    assert_equal(A[[1,3],3].todense(), B[[1,3],3])
    assert_equal(A[[2,-5],-4].todense(), B[[2,-5],-4])
    assert_equal(A[array([2,-5]),-4].todense(), B[[2,-5],-4])
    assert_equal(A[[2,-5],array(-4)].todense(), B[[2,-5],-4])
    assert_equal(A[array([2,-5]),array(-4)].todense(), B[[2,-5],-4])

    # [[1,2],1:2]
    assert_equal(A[[1,3],:].todense(), B[[1,3],:])
    assert_equal(A[[2,-5],8:-1].todense(),B[[2,-5],8:-1])
    assert_equal(A[array([2,-5]),8:-1].todense(),B[[2,-5],8:-1])

    # [[1,2],[1,2]]
    assert_equal(todense(A[[1,3],[2,4]]), B[[1,3],[2,4]])
    assert_equal(todense(A[[-1,-3],[2,-4]]), B[[-1,-3],[2,-4]])
    assert_equal(todense(A[array([-1,-3]),[2,-4]]), B[[-1,-3],[2,-4]])
    assert_equal(todense(A[[-1,-3],array([2,-4])]), B[[-1,-3],[2,-4]])
    assert_equal(todense(A[array([-1,-3]),array([2,-4])]), B[[-1,-3],[2,-4]])

    # [[[1],[2]],[1,2]]
    assert_equal(A[[[1],[3]],[2,4]].todense(), B[[[1],[3]],[2,4]])
    assert_equal(A[[[-1],[-3],[-2]],[2,-4]].todense(),B[[[-1],[-3],[-2]],[2,-4]])
    assert_equal(A[array([[-1],[-3],[-2]]),[2,-4]].todense(),B[[[-1],[-3],[-2]],[2,-4]])
    assert_equal(A[[[-1],[-3],[-2]],array([2,-4])].todense(),B[[[-1],[-3],[-2]],[2,-4]])
    assert_equal(A[array([[-1],[-3],[-2]]),array([2,-4])].todense(),B[[[-1],[-3],[-2]],[2,-4]])

    # [[1,2]]
    assert_equal(A[[1,3]].todense(), B[[1,3]])
    assert_equal(A[[-1,-3]].todense(),B[[-1,-3]])
    assert_equal(A[array([-1,-3])].todense(),B[[-1,-3]])

    # [[1,2],:][:,[1,2]]
    assert_equal(A[[1,3],:][:,[2,4]].todense(), B[[1,3],:][:,[2,4]])
    assert_equal(A[[-1,-3],:][:,[2,-4]].todense(), B[[-1,-3],:][:,[2,-4]])
    assert_equal(A[array([-1,-3]),:][:,array([2,-4])].todense(), B[[-1,-3],:][:,[2,-4]])

    # [:,[1,2]][[1,2],:]
    assert_equal(A[:,[1,3]][[2,4],:].todense(), B[:,[1,3]][[2,4],:])
    assert_equal(A[:,[-1,-3]][[2,-4],:].todense(), B[:,[-1,-3]][[2,-4],:])
    assert_equal(A[:,array([-1,-3])][array([2,-4]),:].todense(), B[:,[-1,-3]][[2,-4],:])

    # Check bug reported by Robert Cimrman:
    # http://thread.gmane.org/gmane.comp.python.scientific.devel/7986
    s = slice(int8(2),int8(4),None)
    assert_equal(A[s,:].todense(), B[2:4,:])
    assert_equal(A[:,s].todense(), B[:,2:4])
