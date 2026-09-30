# smell: LargeClass
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/sparse/tests/test_base.py#L181-L1747
# smelly line(s) in the original file: 181
# smelly line(s) in this file: 8
# ids: pysmell_0333
# note: Python 2 era source, kept as found
class _TestCommon:
    """test common functionality shared by all sparse formats"""
    checked_dtypes = supported_dtypes

    def __init__(self):
        # Canonical data.
        self.dat = matrix([[1,0,0,2],[3,0,1,0],[0,2,0,0]],'d')
        self.datsp = self.spmatrix(self.dat)

        # Some sparse and dense matrices with data for every supported
        # dtype.
        self.dat_dtypes = {}
        self.datsp_dtypes = {}
        for dtype in self.checked_dtypes:
            self.dat_dtypes[dtype] = self.dat.astype(dtype)
            self.datsp_dtypes[dtype] = self.spmatrix(self.dat.astype(dtype))

        # Check that the original data is equivalent to the
        # corresponding dat_dtypes & datsp_dtypes.
        assert_equal(self.dat, self.dat_dtypes[np.float64])
        assert_equal(self.datsp.todense(),
                     self.datsp_dtypes[np.float64].todense())

    def test_bool(self):
        def check(dtype):
            datsp = self.datsp_dtypes[dtype]

            assert_raises(ValueError, bool, datsp)
            assert_(self.spmatrix([1]))
            assert_(not self.spmatrix([0]))
        for dtype in self.checked_dtypes:
            fails = isinstance(self, TestDOK)
            msg = "Cannot create a rank <= 2 DOK matrix."
            yield dec.skipif(fails, msg)(check), dtype

    def test_bool_rollover(self):
        # bool's underlying dtype is 1 byte, check that it does not
        # rollover True -> False at 256.
        dat = np.matrix([[True, False]])
        datsp = self.spmatrix(dat)

        for _ in range(10):
            datsp = datsp + datsp
            dat = dat + dat
        assert_array_equal(dat, datsp.todense())

    def test_eq(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]
            dat2 = dat.copy()
            dat2[:,0] = 0
            datsp2 = self.spmatrix(dat2)
            datbsr = bsr_matrix(dat)
            datcsr = csr_matrix(dat)
            datcsc = csc_matrix(dat)
            datlil = lil_matrix(dat)

            # sparse/sparse
            assert_array_equal(dat == dat2, (datsp == datsp2).todense())
            # mix sparse types
            assert_array_equal(dat == dat2, (datbsr == datsp2).todense())
            assert_array_equal(dat == dat2, (datcsr == datsp2).todense())
            assert_array_equal(dat == dat2, (datcsc == datsp2).todense())
            assert_array_equal(dat == dat2, (datlil == datsp2).todense())
            # sparse/dense
            assert_array_equal(dat == datsp2, datsp2 == dat)
            # sparse/scalar
            assert_array_equal(dat == 0, (datsp == 0).todense())
            assert_array_equal(dat == 1, (datsp == 1).todense())
            assert_array_equal(dat == np.nan, (datsp == np.nan).todense())

        msg = "Bool comparisons only implemented for BSR, CSC, and CSR."
        fails = not isinstance(self, (TestBSR, TestCSC, TestCSR))
        for dtype in self.checked_dtypes:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=np.ComplexWarning)
                warnings.simplefilter("ignore", category=SparseEfficiencyWarning)
                yield dec.skipif(fails, msg)(check), dtype

    def test_ne(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]
            dat2 = dat.copy()
            dat2[:,0] = 0
            datsp2 = self.spmatrix(dat2)
            datbsr = bsr_matrix(dat)
            datcsc = csc_matrix(dat)
            datcsr = csr_matrix(dat)
            datlil = lil_matrix(dat)

            # sparse/sparse
            assert_array_equal(dat != dat2, (datsp != datsp2).todense())
            # mix sparse types
            assert_array_equal(dat != dat2, (datbsr != datsp2).todense())
            assert_array_equal(dat != dat2, (datcsc != datsp2).todense())
            assert_array_equal(dat != dat2, (datcsr != datsp2).todense())
            assert_array_equal(dat != dat2, (datlil != datsp2).todense())
            # sparse/dense
            assert_array_equal(dat != datsp2, datsp2 != dat)
            # sparse/scalar
            assert_array_equal(dat != 0, (datsp != 0).todense())
            assert_array_equal(dat != 1, (datsp != 1).todense())
            assert_array_equal(0 != dat, (0 != datsp).todense())
            assert_array_equal(1 != dat, (1 != datsp).todense())
            assert_array_equal(dat != np.nan, (datsp != np.nan).todense())

        msg = "Bool comparisons only implemented for BSR, CSC, and CSR."
        fails = not isinstance(self, (TestBSR, TestCSC, TestCSR))
        for dtype in self.checked_dtypes:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=np.ComplexWarning)
                warnings.simplefilter("ignore", category=SparseEfficiencyWarning)
                yield dec.skipif(fails, msg)(check), dtype

    def test_lt(self):
        def check(dtype):
            # data
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]
            dat2 = dat.copy()
            dat2[:,0] = 0
            datsp2 = self.spmatrix(dat2)
            datcomplex = dat.astype(np.complex)
            datcomplex[:,0] = 1 + 1j
            datspcomplex = self.spmatrix(datcomplex)
            datbsr = bsr_matrix(dat)
            datcsc = csc_matrix(dat)
            datcsr = csr_matrix(dat)
            datlil = lil_matrix(dat)

            # sparse/sparse
            assert_array_equal(dat < dat2, (datsp < datsp2).todense())
            assert_array_equal(datcomplex < dat2, (datspcomplex < datsp2).todense())
            # mix sparse types
            assert_array_equal(dat < dat2, (datbsr < datsp2).todense())
            assert_array_equal(dat < dat2, (datcsc < datsp2).todense())
            assert_array_equal(dat < dat2, (datcsr < datsp2).todense())
            assert_array_equal(dat < dat2, (datlil < datsp2).todense())

            assert_array_equal(dat2 < dat, (datsp2 < datbsr).todense())
            assert_array_equal(dat2 < dat, (datsp2 < datcsc).todense())
            assert_array_equal(dat2 < dat, (datsp2 < datcsr).todense())
            assert_array_equal(dat2 < dat, (datsp2 < datlil).todense())
            # sparse/dense
            assert_array_equal(dat < dat2, datsp < dat2)
            assert_array_equal(datcomplex < dat2, datspcomplex < dat2)
            # sparse/scalar
            assert_array_equal((datsp < 2).todense(), dat < 2)
            assert_array_equal((datsp < 1).todense(), dat < 1)
            assert_array_equal((datsp < 0).todense(), dat < 0)
            assert_array_equal((datsp < -1).todense(), dat < -1)
            assert_array_equal((datsp < -2).todense(), dat < -2)
            with np.errstate(invalid='ignore'):
                assert_array_equal((datsp < np.nan).todense(), dat < np.nan)

            assert_array_equal((2 < datsp).todense(), 2 < dat)
            assert_array_equal((1 < datsp).todense(), 1 < dat)
            assert_array_equal((0 < datsp).todense(), 0 < dat)
            assert_array_equal((-1 < datsp).todense(), -1 < dat)
            assert_array_equal((-2 < datsp).todense(), -2 < dat)

            if NumpyVersion(np.__version__) >= '1.8.0':
                # data
                dat = self.dat_dtypes[dtype]
                datsp = self.datsp_dtypes[dtype]
                dat2 = dat.copy()
                dat2[:,0] = 0
                datsp2 = self.spmatrix(dat2)

                # dense rhs
                assert_array_equal(dat < datsp2, datsp < dat2)

        msg = "Bool comparisons only implemented for BSR, CSC, and CSR."
        fails = not isinstance(self, (TestBSR, TestCSC, TestCSR))
        for dtype in self.checked_dtypes:
            with warnings.catch_warnings():
                with np.errstate(invalid='ignore'):
                    warnings.simplefilter("ignore", category=np.ComplexWarning)
                    warnings.simplefilter("ignore", category=SparseEfficiencyWarning)
                    yield dec.skipif(fails, msg)(check), dtype

    def test_gt(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]
            dat2 = dat.copy()
            dat2[:,0] = 0
            datsp2 = self.spmatrix(dat2)
            datcomplex = dat.astype(np.complex)
            datcomplex[:,0] = 1 + 1j
            datspcomplex = self.spmatrix(datcomplex)
            datbsr = bsr_matrix(dat)
            datcsc = csc_matrix(dat)
            datcsr = csr_matrix(dat)
            datlil = lil_matrix(dat)

            # sparse/sparse
            assert_array_equal(dat > dat2, (datsp > datsp2).todense())
            assert_array_equal(datcomplex > dat2, (datspcomplex > datsp2).todense())
            # mix sparse types
            assert_array_equal(dat > dat2, (datbsr > datsp2).todense())
            assert_array_equal(dat > dat2, (datcsc > datsp2).todense())
            assert_array_equal(dat > dat2, (datcsr > datsp2).todense())
            assert_array_equal(dat > dat2, (datlil > datsp2).todense())

            assert_array_equal(dat2 > dat, (datsp2 > datbsr).todense())
            assert_array_equal(dat2 > dat, (datsp2 > datcsc).todense())
            assert_array_equal(dat2 > dat, (datsp2 > datcsr).todense())
            assert_array_equal(dat2 > dat, (datsp2 > datlil).todense())
            # sparse/dense
            assert_array_equal(dat > dat2, datsp > dat2)
            assert_array_equal(datcomplex > dat2, datspcomplex > dat2)
            # sparse/scalar
            assert_array_equal((datsp > 2).todense(), dat > 2)
            assert_array_equal((datsp > 1).todense(), dat > 1)
            assert_array_equal((datsp > 0).todense(), dat > 0)
            assert_array_equal((datsp > -1).todense(), dat > -1)
            assert_array_equal((datsp > -2).todense(), dat > -2)
            with np.errstate(invalid='ignore'):
                assert_array_equal((datsp > np.nan).todense(), dat > np.nan)

            assert_array_equal((2 > datsp).todense(), 2 > dat)
            assert_array_equal((1 > datsp).todense(), 1 > dat)
            assert_array_equal((0 > datsp).todense(), 0 > dat)
            assert_array_equal((-1 > datsp).todense(), -1 > dat)
            assert_array_equal((-2 > datsp).todense(), -2 > dat)

            if NumpyVersion(np.__version__) >= '1.8.0':
                # data
                dat = self.dat_dtypes[dtype]
                datsp = self.datsp_dtypes[dtype]
                dat2 = dat.copy()
                dat2[:,0] = 0
                datsp2 = self.spmatrix(dat2)

                # dense rhs
                assert_array_equal(dat > datsp2, datsp > dat2)

        msg = "Bool comparisons only implemented for BSR, CSC, and CSR."
        fails = not isinstance(self, (TestBSR, TestCSC, TestCSR))
        for dtype in self.checked_dtypes:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=np.ComplexWarning)
                warnings.simplefilter("ignore", category=SparseEfficiencyWarning)
                yield dec.skipif(fails, msg)(check), dtype

    def test_le(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]
            dat2 = dat.copy()
            dat2[:,0] = 0
            datsp2 = self.spmatrix(dat2)
            datcomplex = dat.astype(np.complex)
            datcomplex[:,0] = 1 + 1j
            datspcomplex = self.spmatrix(datcomplex)
            datbsr = bsr_matrix(dat)
            datcsc = csc_matrix(dat)
            datcsr = csr_matrix(dat)
            datlil = lil_matrix(dat)

            # sparse/sparse
            assert_array_equal(dat <= dat2, (datsp <= datsp2).todense())
            assert_array_equal(datcomplex <= dat2, (datspcomplex <= datsp2).todense())
            # mix sparse types
            assert_array_equal((datbsr <= datsp2).todense(), dat <= dat2)
            assert_array_equal((datcsc <= datsp2).todense(), dat <= dat2)
            assert_array_equal((datcsr <= datsp2).todense(), dat <= dat2)
            assert_array_equal((datlil <= datsp2).todense(), dat <= dat2)

            assert_array_equal((datsp2 <= datbsr).todense(), dat2 <= dat)
            assert_array_equal((datsp2 <= datcsc).todense(), dat2 <= dat)
            assert_array_equal((datsp2 <= datcsr).todense(), dat2 <= dat)
            assert_array_equal((datsp2 <= datlil).todense(), dat2 <= dat)
            # sparse/dense
            assert_array_equal(datsp <= dat2, dat <= dat2)
            assert_array_equal(datspcomplex <= dat2, datcomplex <= dat2)
            # sparse/scalar
            assert_array_equal((datsp <= 2).todense(), dat <= 2)
            assert_array_equal((datsp <= 1).todense(), dat <= 1)
            assert_array_equal((datsp <= -1).todense(), dat <= -1)
            assert_array_equal((datsp <= -2).todense(), dat <= -2)

            assert_array_equal((2 <= datsp).todense(), 2 <= dat)
            assert_array_equal((1 <= datsp).todense(), 1 <= dat)
            assert_array_equal((-1 <= datsp).todense(), -1 <= dat)
            assert_array_equal((-2 <= datsp).todense(), -2 <= dat)

            if NumpyVersion(np.__version__) >= '1.8.0':
                # data
                dat = self.dat_dtypes[dtype]
                datsp = self.datsp_dtypes[dtype]
                dat2 = dat.copy()
                dat2[:,0] = 0
                datsp2 = self.spmatrix(dat2)

                # dense rhs
                assert_array_equal(dat <= datsp2, datsp <= dat2)

        msg = "Bool comparisons only implemented for BSR, CSC, and CSR."
        fails = not isinstance(self, (TestBSR, TestCSC, TestCSR))
        for dtype in self.checked_dtypes:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=np.ComplexWarning)
                warnings.simplefilter("ignore", category=SparseEfficiencyWarning)
                yield dec.skipif(fails, msg)(check), dtype

    def test_ge(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]
            dat2 = dat.copy()
            dat2[:,0] = 0
            datsp2 = self.spmatrix(dat2)
            datcomplex = dat.astype(np.complex)
            datcomplex[:,0] = 1 + 1j
            datspcomplex = self.spmatrix(datcomplex)
            datbsr = bsr_matrix(dat)
            datcsc = csc_matrix(dat)
            datcsr = csr_matrix(dat)
            datlil = lil_matrix(dat)

            # sparse/sparse
            assert_array_equal(dat >= dat2, (datsp >= datsp2).todense())
            assert_array_equal(datcomplex >= dat2, (datspcomplex >= datsp2).todense())
            # mix sparse types
            # mix sparse types
            assert_array_equal((datbsr >= datsp2).todense(), dat >= dat2)
            assert_array_equal((datcsc >= datsp2).todense(), dat >= dat2)
            assert_array_equal((datcsr >= datsp2).todense(), dat >= dat2)
            assert_array_equal((datlil >= datsp2).todense(), dat >= dat2)

            assert_array_equal((datsp2 >= datbsr).todense(), dat2 >= dat)
            assert_array_equal((datsp2 >= datcsc).todense(), dat2 >= dat)
            assert_array_equal((datsp2 >= datcsr).todense(), dat2 >= dat)
            assert_array_equal((datsp2 >= datlil).todense(), dat2 >= dat)
            # sparse/dense
            assert_array_equal(datsp >= dat2, dat >= dat2)
            assert_array_equal(datspcomplex >= dat2, datcomplex >= dat2)
            # sparse/scalar
            assert_array_equal((datsp >= 2).todense(), dat >= 2)
            assert_array_equal((datsp >= 1).todense(), dat >= 1)
            assert_array_equal((datsp >= -1).todense(), dat >= -1)
            assert_array_equal((datsp >= -2).todense(), dat >= -2)

            assert_array_equal((2 >= datsp).todense(), 2 >= dat)
            assert_array_equal((1 >= datsp).todense(), 1 >= dat)
            assert_array_equal((-1 >= datsp).todense(), -1 >= dat)
            assert_array_equal((-2 >= datsp).todense(), -2 >= dat)

            if NumpyVersion(np.__version__) >= '1.8.0':
                # dense data
                dat = self.dat_dtypes[dtype]
                datsp = self.datsp_dtypes[dtype]
                dat2 = dat.copy()
                dat2[:,0] = 0
                datsp2 = self.spmatrix(dat2)

                # dense rhs
                assert_array_equal(dat >= datsp2, datsp >= dat2)

        msg = "Bool comparisons only implemented for BSR, CSC, and CSR."
        fails = not isinstance(self, (TestBSR, TestCSC, TestCSR))
        for dtype in self.checked_dtypes:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=np.ComplexWarning)
                warnings.simplefilter("ignore", category=SparseEfficiencyWarning)
                yield dec.skipif(fails, msg)(check), dtype

    def test_empty(self):
        # create empty matrices
        assert_equal(self.spmatrix((3,3)).todense(), np.zeros((3,3)))
        assert_equal(self.spmatrix((3,3)).nnz, 0)

    def test_invalid_shapes(self):
        assert_raises(ValueError, self.spmatrix, (-1,3))
        assert_raises(ValueError, self.spmatrix, (3,-1))
        assert_raises(ValueError, self.spmatrix, (-1,-1))

    def test_repr(self):
        repr(self.datsp)

    def test_str(self):
        str(self.datsp)

    def test_empty_arithmetic(self):
        # Test manipulating empty matrices. Fails in SciPy SVN <= r1768
        shape = (5, 5)
        for mytype in [np.dtype('int32'), np.dtype('float32'),
                np.dtype('float64'), np.dtype('complex64'),
                np.dtype('complex128')]:
            a = self.spmatrix(shape, dtype=mytype)
            b = a + a
            c = 2 * a
            d = a * a.tocsc()
            e = a * a.tocsr()
            f = a * a.tocoo()
            for m in [a,b,c,d,e,f]:
                assert_equal(m.A, a.A*a.A)
                # These fail in all revisions <= r1768:
                assert_equal(m.dtype,mytype)
                assert_equal(m.A.dtype,mytype)

    def test_abs(self):
        A = matrix([[-1, 0, 17],[0, -5, 0],[1, -4, 0],[0,0,0]],'d')
        assert_equal(abs(A),abs(self.spmatrix(A)).todense())

    def test_elementwise_power(self):
        A = matrix([[-4, -3, -2],[-1, 0, 1],[2, 3, 4]], 'd')        
        assert_equal(np.power(A, 2), self.spmatrix(A).power(2).todense())

        #it's element-wise power function, input has to be a scalar
        assert_raises(NotImplementedError, self.spmatrix(A).power, A)       

    def test_neg(self):
        A = matrix([[-1, 0, 17],[0, -5, 0],[1, -4, 0],[0,0,0]],'d')
        assert_equal(-A,(-self.spmatrix(A)).todense())

    def test_real(self):
        D = matrix([[1 + 3j, 2 - 4j]])
        A = self.spmatrix(D)
        assert_equal(A.real.todense(),D.real)

    def test_imag(self):
        D = matrix([[1 + 3j, 2 - 4j]])
        A = self.spmatrix(D)
        assert_equal(A.imag.todense(),D.imag)

    def test_diagonal(self):
        # Does the matrix's .diagonal() method work?
        mats = []
        mats.append([[1,0,2]])
        mats.append([[1],[0],[2]])
        mats.append([[0,1],[0,2],[0,3]])
        mats.append([[0,0,1],[0,0,2],[0,3,0]])

        mats.append(kron(mats[0],[[1,2]]))
        mats.append(kron(mats[0],[[1],[2]]))
        mats.append(kron(mats[1],[[1,2],[3,4]]))
        mats.append(kron(mats[2],[[1,2],[3,4]]))
        mats.append(kron(mats[3],[[1,2],[3,4]]))
        mats.append(kron(mats[3],[[1,2,3,4]]))

        for m in mats:
            assert_equal(self.spmatrix(m).diagonal(),diag(m))        

    @dec.slow
    def test_setdiag(self):
        def dense_setdiag(a, v, k):
            v = np.asarray(v)
            if k >= 0:
                n = min(a.shape[0], a.shape[1] - k)
                if v.ndim != 0:
                    n = min(n, len(v))
                    v = v[:n]
                i = np.arange(0, n)
                j = np.arange(k, k + n)
                a[i,j] = v
            elif k < 0:
                dense_setdiag(a.T, v, -k)
                return

        def check_setdiag(a, b, k):
            # Check setting diagonal using a scalar, a vector of
            # correct length, and too short or too long vectors
            for r in [-1, len(np.diag(a, k)), 2, 30]:
                if r < 0:
                    v = int(np.random.randint(1, 20, size=1))
                else:
                    v = np.random.randint(1, 20, size=r)

                dense_setdiag(a, v, k)
                b.setdiag(v, k)

                # check that dense_setdiag worked
                d = np.diag(a, k)
                if np.asarray(v).ndim == 0:
                    assert_array_equal(d, v, err_msg=msg + " %d" % (r,))
                else:
                    n = min(len(d), len(v))
                    assert_array_equal(d[:n], v[:n], err_msg=msg + " %d" % (r,))
                # check that sparse setdiag worked
                assert_array_equal(b.A, a, err_msg=msg + " %d" % (r,))

        # comprehensive test
        np.random.seed(1234)
        for dtype in [np.int8, np.float64]:
            for m in [0, 1, 3, 10]:
                for n in [0, 1, 3, 10]:
                    for k in range(-m+1, n-1):
                        msg = repr((dtype, m, n, k))
                        a = np.zeros((m, n), dtype=dtype)
                        b = self.spmatrix((m, n), dtype=dtype)

                        check_setdiag(a, b, k)

                        # check overwriting etc
                        for k2 in np.random.randint(-m+1, n-1, size=12):
                            check_setdiag(a, b, k2)

        # simpler test case
        m = self.spmatrix(np.eye(3))
        values = [3, 2, 1]
        assert_raises(ValueError, m.setdiag, values, k=4)
        m.setdiag(values)
        assert_array_equal(m.diagonal(), values)
        m.setdiag(values, k=1)
        assert_array_equal(m.A, np.array([[3, 3, 0],
                                          [0, 2, 2],
                                          [0, 0, 1]]))
        m.setdiag(values, k=-2)
        assert_array_equal(m.A, np.array([[3, 3, 0],
                                          [0, 2, 2],
                                          [3, 0, 1]]))
        m.setdiag((9,), k=2)
        assert_array_equal(m.A[0,2], 9)
        m.setdiag((9,), k=-2)
        assert_array_equal(m.A[2,0], 9)

    def test_nonzero(self):
        A = array([[1, 0, 1],[0, 1, 1],[0, 0, 1]])
        Asp = self.spmatrix(A)

        A_nz = set([tuple(ij) for ij in transpose(A.nonzero())])
        Asp_nz = set([tuple(ij) for ij in transpose(Asp.nonzero())])

        assert_equal(A_nz, Asp_nz)

    def test_getrow(self):
        assert_array_equal(self.datsp.getrow(1).todense(), self.dat[1,:])
        assert_array_equal(self.datsp.getrow(-1).todense(), self.dat[-1,:])

    def test_getcol(self):
        assert_array_equal(self.datsp.getcol(1).todense(), self.dat[:,1])
        assert_array_equal(self.datsp.getcol(-1).todense(), self.dat[:,-1])

    def test_sum(self):
        np.random.seed(1234)
        dat_1 = np.matrix([[0, 1, 2],
                           [3, -4, 5],
                           [-6, 7, 9]])
        dat_2 = np.random.rand(40, 40)
        dat_3 = np.array([[]])
        dat_4 = np.zeros((40, 40))
        dat_5 = sparse.rand(40, 40, density=1e-2).A
        matrices = [dat_1, dat_2, dat_3, dat_4, dat_5]

        def check(dtype, j):
            dat = np.matrix(matrices[j], dtype=dtype)
            datsp = self.spmatrix(dat, dtype=dtype)

            assert_array_almost_equal(dat.sum(), datsp.sum())
            assert_equal(dat.sum().dtype, datsp.sum().dtype)
            assert_array_almost_equal(dat.sum(axis=None), datsp.sum(axis=None))
            assert_equal(dat.sum(axis=None).dtype, datsp.sum(axis=None).dtype)
            assert_array_almost_equal(dat.sum(axis=0), datsp.sum(axis=0))
            assert_equal(dat.sum(axis=0).dtype, datsp.sum(axis=0).dtype)
            assert_array_almost_equal(dat.sum(axis=1), datsp.sum(axis=1))
            assert_equal(dat.sum(axis=1).dtype, datsp.sum(axis=1).dtype)
            if NumpyVersion(np.__version__) >= '1.7.0':
                # np.matrix.sum with negative axis arg doesn't work for < 1.7
                assert_array_almost_equal(dat.sum(axis=-2), datsp.sum(axis=-2))
                assert_equal(dat.sum(axis=-2).dtype, datsp.sum(axis=-2).dtype)
                assert_array_almost_equal(dat.sum(axis=-1), datsp.sum(axis=-1))
                assert_equal(dat.sum(axis=-1).dtype, datsp.sum(axis=-1).dtype)

        for dtype in self.checked_dtypes:
            for j in range(len(matrices)):
                yield check, dtype, j

    def test_mean(self):
        def check(dtype):
            dat = np.matrix([[0, 1, 2],
                            [3, -4, 5],
                            [-6, 7, 9]], dtype=dtype)
            datsp = self.spmatrix(dat, dtype=dtype)

            assert_array_almost_equal(dat.mean(), datsp.mean())
            assert_equal(dat.mean().dtype, datsp.mean().dtype)
            assert_array_almost_equal(dat.mean(axis=None), datsp.mean(axis=None))
            assert_equal(dat.mean(axis=None).dtype, datsp.mean(axis=None).dtype)
            assert_array_almost_equal(dat.mean(axis=0), datsp.mean(axis=0))
            assert_equal(dat.mean(axis=0).dtype, datsp.mean(axis=0).dtype)
            assert_array_almost_equal(dat.mean(axis=1), datsp.mean(axis=1))
            assert_equal(dat.mean(axis=1).dtype, datsp.mean(axis=1).dtype)
            if NumpyVersion(np.__version__) >= '1.7.0':
                # np.matrix.sum with negative axis arg doesn't work for < 1.7
                assert_array_almost_equal(dat.mean(axis=-2), datsp.mean(axis=-2))
                assert_equal(dat.mean(axis=-2).dtype, datsp.mean(axis=-2).dtype)
                assert_array_almost_equal(dat.mean(axis=-1), datsp.mean(axis=-1))
                assert_equal(dat.mean(axis=-1).dtype, datsp.mean(axis=-1).dtype)

        for dtype in self.checked_dtypes:
            yield check, dtype

    def test_expm(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=SparseEfficiencyWarning)

            M = array([[1, 0, 2], [0, 0, 3], [-4, 5, 6]], float)
            sM = self.spmatrix(M, shape=(3,3), dtype=float)
            Mexp = scipy.linalg.expm(M)
            sMexp = expm(sM).todense()
            assert_array_almost_equal((sMexp - Mexp), zeros((3, 3)))

            N = array([[3., 0., 1.], [0., 2., 0.], [0., 0., 0.]])
            sN = self.spmatrix(N, shape=(3,3), dtype=float)
            Nexp = scipy.linalg.expm(N)
            sNexp = expm(sN).todense()
            assert_array_almost_equal((sNexp - Nexp), zeros((3, 3)))

    def test_inv(self):
        def check(dtype):
            M = array([[1, 0, 2], [0, 0, 3], [-4, 5, 6]], dtype)
            sM = self.spmatrix(M, shape=(3,3), dtype=dtype)
            sMinv = inv(sM)
            assert_array_almost_equal(sMinv.dot(sM).todense(), np.eye(3))
        for dtype in [float]:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=SparseEfficiencyWarning)
                yield check, dtype

    def test_from_array(self):
        A = array([[1,0,0],[2,3,4],[0,5,0],[0,0,0]])
        assert_array_equal(self.spmatrix(A).toarray(), A)

        A = array([[1.0 + 3j, 0, 0],
                   [0, 2.0 + 5, 0],
                   [0, 0, 0]])
        assert_array_equal(self.spmatrix(A).toarray(), A)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=np.ComplexWarning)
            assert_array_equal(self.spmatrix(A, dtype='int16').toarray(), A.astype('int16'))

    def test_from_matrix(self):
        A = matrix([[1,0,0],[2,3,4],[0,5,0],[0,0,0]])
        assert_array_equal(self.spmatrix(A).todense(), A)

        A = matrix([[1.0 + 3j, 0, 0],
                    [0, 2.0 + 5, 0],
                    [0, 0, 0]])
        assert_array_equal(self.spmatrix(A).toarray(), A)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=np.ComplexWarning)
            assert_array_equal(self.spmatrix(A, dtype='int16').toarray(), A.astype('int16'))

    def test_from_list(self):
        A = [[1,0,0],[2,3,4],[0,5,0],[0,0,0]]
        assert_array_equal(self.spmatrix(A).todense(), A)

        A = [[1.0 + 3j, 0, 0],
             [0, 2.0 + 5, 0],
             [0, 0, 0]]
        assert_array_equal(self.spmatrix(A).toarray(), array(A))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=np.ComplexWarning)
            assert_array_equal(self.spmatrix(A, dtype='int16').todense(), array(A).astype('int16'))

    def test_from_sparse(self):
        D = array([[1,0,0],[2,3,4],[0,5,0],[0,0,0]])
        S = csr_matrix(D)
        assert_array_equal(self.spmatrix(S).toarray(), D)
        S = self.spmatrix(D)
        assert_array_equal(self.spmatrix(S).toarray(), D)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=np.ComplexWarning)
            D = array([[1.0 + 3j, 0, 0],
                       [0, 2.0 + 5, 0],
                       [0, 0, 0]])
            S = csr_matrix(D)
            assert_array_equal(self.spmatrix(S).toarray(), D)
            assert_array_equal(self.spmatrix(S, dtype='int16').toarray(), D.astype('int16'))
            S = self.spmatrix(D)
            assert_array_equal(self.spmatrix(S).toarray(), D)
            assert_array_equal(self.spmatrix(S, dtype='int16').toarray(), D.astype('int16'))

    # def test_array(self):
    #    """test array(A) where A is in sparse format"""
    #    assert_equal( array(self.datsp), self.dat )

    def test_todense(self):
        # Check C-contiguous (default).
        chk = self.datsp.todense()
        assert_array_equal(chk, self.dat)
        assert_(chk.flags.c_contiguous)
        assert_(not chk.flags.f_contiguous)
        # Check C-contiguous (with arg).
        chk = self.datsp.todense(order='C')
        assert_array_equal(chk, self.dat)
        assert_(chk.flags.c_contiguous)
        assert_(not chk.flags.f_contiguous)
        # Check F-contiguous (with arg).
        chk = self.datsp.todense(order='F')
        assert_array_equal(chk, self.dat)
        assert_(not chk.flags.c_contiguous)
        assert_(chk.flags.f_contiguous)
        # Check with out argument (array).
        out = np.zeros(self.datsp.shape, dtype=self.datsp.dtype)
        chk = self.datsp.todense(out=out)
        assert_array_equal(self.dat, out)
        assert_array_equal(self.dat, chk)
        assert_(chk.base is out)
        # Check with out array (matrix).
        out = np.asmatrix(np.zeros(self.datsp.shape, dtype=self.datsp.dtype))
        chk = self.datsp.todense(out=out)
        assert_array_equal(self.dat, out)
        assert_array_equal(self.dat, chk)
        assert_(chk is out)
        a = matrix([1.,2.,3.])
        dense_dot_dense = a * self.dat
        check = a * self.datsp.todense()
        assert_array_equal(dense_dot_dense, check)
        b = matrix([1.,2.,3.,4.]).T
        dense_dot_dense = self.dat * b
        check2 = self.datsp.todense() * b
        assert_array_equal(dense_dot_dense, check2)
        # Check bool data works.
        spbool = self.spmatrix(self.dat, dtype=bool)
        matbool = self.dat.astype(bool)
        assert_array_equal(spbool.todense(), matbool)

    def test_toarray(self):
        # Check C-contiguous (default).
        dat = asarray(self.dat)
        chk = self.datsp.toarray()
        assert_array_equal(chk, dat)
        assert_(chk.flags.c_contiguous)
        assert_(not chk.flags.f_contiguous)
        # Check C-contiguous (with arg).
        chk = self.datsp.toarray(order='C')
        assert_array_equal(chk, dat)
        assert_(chk.flags.c_contiguous)
        assert_(not chk.flags.f_contiguous)
        # Check F-contiguous (with arg).
        chk = self.datsp.toarray(order='F')
        assert_array_equal(chk, dat)
        assert_(not chk.flags.c_contiguous)
        assert_(chk.flags.f_contiguous)
        # Check with output arg.
        out = np.zeros(self.datsp.shape, dtype=self.datsp.dtype)
        self.datsp.toarray(out=out)
        assert_array_equal(chk, dat)
        # Check that things are fine when we don't initialize with zeros.
        out[...] = 1.
        self.datsp.toarray(out=out)
        assert_array_equal(chk, dat)
        a = array([1.,2.,3.])
        dense_dot_dense = dot(a, dat)
        check = dot(a, self.datsp.toarray())
        assert_array_equal(dense_dot_dense, check)
        b = array([1.,2.,3.,4.])
        dense_dot_dense = dot(dat, b)
        check2 = dot(self.datsp.toarray(), b)
        assert_array_equal(dense_dot_dense, check2)
        # Check bool data works.
        spbool = self.spmatrix(self.dat, dtype=bool)
        arrbool = dat.astype(bool)
        assert_array_equal(spbool.toarray(), arrbool)

    def test_astype(self):
        D = array([[2.0 + 3j, 0, 0],
                   [0, 4.0 + 5j, 0],
                   [0, 0, 0]])
        S = self.spmatrix(D)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=np.ComplexWarning)

            for x in supported_dtypes:
                assert_equal(S.astype(x).dtype, D.astype(x).dtype)  # correct type
                assert_equal(S.astype(x).toarray(), D.astype(x))        # correct values
                assert_equal(S.astype(x).format, S.format)           # format preserved

    def test_asfptype(self):
        A = self.spmatrix(arange(6,dtype='int32').reshape(2,3))

        assert_equal(A.dtype, np.dtype('int32'))
        assert_equal(A.asfptype().dtype, np.dtype('float64'))
        assert_equal(A.asfptype().format, A.format)
        assert_equal(A.astype('int16').asfptype().dtype, np.dtype('float32'))
        assert_equal(A.astype('complex128').asfptype().dtype, np.dtype('complex128'))

        B = A.asfptype()
        C = B.asfptype()
        assert_(B is C)

    def test_mul_scalar(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            assert_array_equal(dat*2,(datsp*2).todense())
            assert_array_equal(dat*17.3,(datsp*17.3).todense())

        for dtype in self.checked_dtypes:
            yield check, dtype

    def test_rmul_scalar(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            assert_array_equal(2*dat,(2*datsp).todense())
            assert_array_equal(17.3*dat,(17.3*datsp).todense())

        for dtype in self.checked_dtypes:
            yield check, dtype

    def test_add(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            a = dat.copy()
            a[0,2] = 2.0
            b = datsp
            c = b + a
            assert_array_equal(c, b.todense() + a)

            c = b + b.tocsr()
            assert_array_equal(c.todense(),
                               b.todense() + b.todense())

        for dtype in self.checked_dtypes:
            yield check, dtype

    def test_radd(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            a = dat.copy()
            a[0,2] = 2.0
            b = datsp
            c = a + b
            assert_array_equal(c, a + b.todense())

        for dtype in self.checked_dtypes:
            yield check, dtype

    def test_sub(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            assert_array_equal((datsp - datsp).todense(),[[0,0,0,0],[0,0,0,0],[0,0,0,0]])

            A = self.spmatrix(matrix([[1,0,0,4],[-1,0,0,0],[0,8,0,-5]],'d'))
            assert_array_equal((datsp - A).todense(),dat - A.todense())
            assert_array_equal((A - datsp).todense(),A.todense() - dat)

        for dtype in self.checked_dtypes:
            yield check, dtype

    def test_rsub(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            assert_array_equal((dat - datsp),[[0,0,0,0],[0,0,0,0],[0,0,0,0]])
            assert_array_equal((datsp - dat),[[0,0,0,0],[0,0,0,0],[0,0,0,0]])

            A = self.spmatrix(matrix([[1,0,0,4],[-1,0,0,0],[0,8,0,-5]],'d'))
            assert_array_equal((dat - A),dat - A.todense())
            assert_array_equal((A - dat),A.todense() - dat)
            assert_array_equal(A.todense() - datsp,A.todense() - dat)
            assert_array_equal(datsp - A.todense(),dat - A.todense())

        for dtype in self.checked_dtypes:
            if (dtype == np.dtype('bool')) and (
                    NumpyVersion(np.__version__) >= '1.9.0.dev'):
                # boolean array subtraction deprecated in 1.9.0
                continue

            yield check, dtype

    def test_add0(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            # Adding 0 to a sparse matrix
            assert_array_equal((datsp + 0).todense(), dat)
            # use sum (which takes 0 as a starting value)
            sumS = sum([k * datsp for k in range(1, 3)])
            sumD = sum([k * dat for k in range(1, 3)])
            assert_almost_equal(sumS.todense(), sumD)

        for dtype in self.checked_dtypes:
            yield check, dtype

    def test_elementwise_multiply(self):
        # real/real
        A = array([[4,0,9],[2,-3,5]])
        B = array([[0,7,0],[0,-4,0]])
        Asp = self.spmatrix(A)
        Bsp = self.spmatrix(B)
        assert_almost_equal(Asp.multiply(Bsp).todense(), A*B)  # sparse/sparse
        assert_almost_equal(Asp.multiply(B), A*B)  # sparse/dense

        # complex/complex
        C = array([[1-2j,0+5j,-1+0j],[4-3j,-3+6j,5]])
        D = array([[5+2j,7-3j,-2+1j],[0-1j,-4+2j,9]])
        Csp = self.spmatrix(C)
        Dsp = self.spmatrix(D)
        assert_almost_equal(Csp.multiply(Dsp).todense(), C*D)  # sparse/sparse
        assert_almost_equal(Csp.multiply(D), C*D)  # sparse/dense

        # real/complex
        assert_almost_equal(Asp.multiply(Dsp).todense(), A*D)  # sparse/sparse
        assert_almost_equal(Asp.multiply(D), A*D)  # sparse/dense

    def test_elementwise_multiply_broadcast(self):
        A = array([4])
        B = array([[-9]])
        C = array([1,-1,0])
        D = array([[7,9,-9]])
        E = array([[3],[2],[1]])
        F = array([[8,6,3],[-4,3,2],[6,6,6]])
        G = [1, 2, 3]
        H = np.ones((3, 4))
        J = H.T

        # Rank 1 arrays can't be cast as spmatrices (A and C) so leave
        # them out.
        Bsp = self.spmatrix(B)
        Dsp = self.spmatrix(D)
        Esp = self.spmatrix(E)
        Fsp = self.spmatrix(F)
        Hsp = self.spmatrix(H)
        Hspp = self.spmatrix(H[0,None])
        Jsp = self.spmatrix(J)
        Jspp = self.spmatrix(J[:,0,None])

        matrices = [A, B, C, D, E, F, G, H, J]
        spmatrices = [Bsp, Dsp, Esp, Fsp, Hsp, Hspp, Jsp, Jspp]

        # sparse/sparse
        for i in spmatrices:
            for j in spmatrices:
                try:
                    dense_mult = np.multiply(i.todense(), j.todense())
                except ValueError:
                    assert_raises(ValueError, i.multiply, j)
                    continue
                sp_mult = i.multiply(j)
                if isspmatrix(sp_mult):
                    assert_almost_equal(sp_mult.todense(), dense_mult)
                else:
                    assert_almost_equal(sp_mult, dense_mult)

        # sparse/dense
        for i in spmatrices:
            for j in matrices:
                try:
                    dense_mult = np.multiply(i.todense(), j)
                except ValueError:
                    assert_raises(ValueError, i.multiply, j)
                    continue
                sp_mult = i.multiply(j)
                if isspmatrix(sp_mult):
                    assert_almost_equal(sp_mult.todense(), dense_mult)
                else:
                    assert_almost_equal(sp_mult, dense_mult)

    def test_elementwise_divide(self):
        expected = [[1,np.nan,np.nan,1],[1,np.nan,1,np.nan],[np.nan,1,np.nan,np.nan]]
        assert_array_equal(todense(self.datsp / self.datsp),expected)

        denom = self.spmatrix(matrix([[1,0,0,4],[-1,0,0,0],[0,8,0,-5]],'d'))
        res = matrix([[1,np.nan,np.nan,0.5],[-3,np.nan,inf,np.nan],[np.nan,0.25,np.nan,np.nan]],'d')
        assert_array_equal(todense(self.datsp / denom),res)

        # complex
        A = array([[1-2j,0+5j,-1+0j],[4-3j,-3+6j,5]])
        B = array([[5+2j,7-3j,-2+1j],[0-1j,-4+2j,9]])
        Asp = self.spmatrix(A)
        Bsp = self.spmatrix(B)
        assert_almost_equal(todense(Asp / Bsp), A/B)

    def test_pow(self):
        A = matrix([[1,0,2,0],[0,3,4,0],[0,5,0,0],[0,6,7,8]])
        B = self.spmatrix(A)

        for exponent in [0,1,2,3]:
            assert_array_equal((B**exponent).todense(),A**exponent)

        # invalid exponents
        for exponent in [-1, 2.2, 1 + 3j]:
            assert_raises(Exception, B.__pow__, exponent)

        # nonsquare matrix
        B = self.spmatrix(A[:3,:])
        assert_raises(Exception, B.__pow__, 1)

    def test_rmatvec(self):
        M = self.spmatrix(matrix([[3,0,0],[0,1,0],[2,0,3.0],[2,3,0]]))
        assert_array_almost_equal([1,2,3,4]*M, dot([1,2,3,4], M.toarray()))
        row = matrix([[1,2,3,4]])
        assert_array_almost_equal(row*M, row*M.todense())

    def test_small_multiplication(self):
        # test that A*x works for x with shape () (1,) and (1,1)
        A = self.spmatrix([[1],[2],[3]])

        assert_(isspmatrix(A * array(1)))
        assert_equal((A * array(1)).todense(), [[1],[2],[3]])
        assert_equal(A * array([1]), array([1,2,3]))
        assert_equal(A * array([[1]]), array([[1],[2],[3]]))

    def test_binop_custom_type(self):
        # Non-regression test: previously, binary operations would raise
        # NotImplementedError instead of returning NotImplemented
        # (https://docs.python.org/library/constants.html#NotImplemented)
        # so overloading Custom + matrix etc. didn't work.
        A = self.spmatrix([[1], [2], [3]])
        B = BinopTester()
        assert_equal(A + B, "matrix on the left")
        assert_equal(A - B, "matrix on the left")
        assert_equal(A * B, "matrix on the left")
        assert_equal(B + A, "matrix on the right")
        assert_equal(B - A, "matrix on the right")
        assert_equal(B * A, "matrix on the right")

    def test_matvec(self):
        M = self.spmatrix(matrix([[3,0,0],[0,1,0],[2,0,3.0],[2,3,0]]))
        col = matrix([1,2,3]).T
        assert_array_almost_equal(M * col, M.todense() * col)

        # check result dimensions (ticket #514)
        assert_equal((M * array([1,2,3])).shape,(4,))
        assert_equal((M * array([[1],[2],[3]])).shape,(4,1))
        assert_equal((M * matrix([[1],[2],[3]])).shape,(4,1))

        # check result type
        assert_(isinstance(M * array([1,2,3]), ndarray))
        assert_(isinstance(M * matrix([1,2,3]).T, matrix))

        # ensure exception is raised for improper dimensions
        bad_vecs = [array([1,2]), array([1,2,3,4]), array([[1],[2]]),
                    matrix([1,2,3]), matrix([[1],[2]])]
        for x in bad_vecs:
            assert_raises(ValueError, M.__mul__, x)

        # Should this be supported or not?!
        # flat = array([1,2,3])
        # assert_array_almost_equal(M*flat, M.todense()*flat)
        # Currently numpy dense matrices promote the result to a 1x3 matrix,
        # whereas sparse matrices leave the result as a rank-1 array.  Which
        # is preferable?

        # Note: the following command does not work.  Both NumPy matrices
        # and spmatrices should raise exceptions!
        # assert_array_almost_equal(M*[1,2,3], M.todense()*[1,2,3])

        # The current relationship between sparse matrix products and array
        # products is as follows:
        assert_array_almost_equal(M*array([1,2,3]), dot(M.A,[1,2,3]))
        assert_array_almost_equal(M*[[1],[2],[3]], asmatrix(dot(M.A,[1,2,3])).T)
        # Note that the result of M * x is dense if x has a singleton dimension.

        # Currently M.matvec(asarray(col)) is rank-1, whereas M.matvec(col)
        # is rank-2.  Is this desirable?

    def test_matmat_sparse(self):
        a = matrix([[3,0,0],[0,1,0],[2,0,3.0],[2,3,0]])
        a2 = array([[3,0,0],[0,1,0],[2,0,3.0],[2,3,0]])
        b = matrix([[0,1],[1,0],[0,2]],'d')
        asp = self.spmatrix(a)
        bsp = self.spmatrix(b)
        assert_array_almost_equal((asp*bsp).todense(), a*b)
        assert_array_almost_equal(asp*b, a*b)
        assert_array_almost_equal(a*bsp, a*b)
        assert_array_almost_equal(a2*bsp, a*b)

        # Now try performing cross-type multplication:
        csp = bsp.tocsc()
        c = b
        assert_array_almost_equal((asp*csp).todense(), a*c)
        assert_array_almost_equal(asp*c, a*c)

        assert_array_almost_equal(a*csp, a*c)
        assert_array_almost_equal(a2*csp, a*c)
        csp = bsp.tocsr()
        assert_array_almost_equal((asp*csp).todense(), a*c)
        assert_array_almost_equal(asp*c, a*c)

        assert_array_almost_equal(a*csp, a*c)
        assert_array_almost_equal(a2*csp, a*c)
        csp = bsp.tocoo()
        assert_array_almost_equal((asp*csp).todense(), a*c)
        assert_array_almost_equal(asp*c, a*c)

        assert_array_almost_equal(a*csp, a*c)
        assert_array_almost_equal(a2*csp, a*c)

        # Test provided by Andy Fraser, 2006-03-26
        L = 30
        frac = .3
        random.seed(0)  # make runs repeatable
        A = zeros((L,2))
        for i in xrange(L):
            for j in xrange(2):
                r = random.random()
                if r < frac:
                    A[i,j] = r/frac

        A = self.spmatrix(A)
        B = A*A.T
        assert_array_almost_equal(B.todense(), A.todense() * A.T.todense())
        assert_array_almost_equal(B.todense(), A.todense() * A.todense().T)

        # check dimension mismatch  2x2 times 3x2
        A = self.spmatrix([[1,2],[3,4]])
        B = self.spmatrix([[1,2],[3,4],[5,6]])
        assert_raises(ValueError, A.__mul__, B)

    def test_matmat_dense(self):
        a = matrix([[3,0,0],[0,1,0],[2,0,3.0],[2,3,0]])
        asp = self.spmatrix(a)

        # check both array and matrix types
        bs = [array([[1,2],[3,4],[5,6]]), matrix([[1,2],[3,4],[5,6]])]

        for b in bs:
            result = asp*b
            assert_(isinstance(result, type(b)))
            assert_equal(result.shape, (4,2))
            assert_equal(result, dot(a,b))

    def test_sparse_format_conversions(self):
        A = sparse.kron([[1,0,2],[0,3,4],[5,0,0]], [[1,2],[0,3]])
        D = A.todense()
        A = self.spmatrix(A)

        for format in ['bsr','coo','csc','csr','dia','dok','lil']:
            a = A.asformat(format)
            assert_equal(a.format,format)
            assert_array_equal(a.todense(), D)

            b = self.spmatrix(D+3j).asformat(format)
            assert_equal(b.format,format)
            assert_array_equal(b.todense(), D+3j)

            c = eval(format + '_matrix')(A)
            assert_equal(c.format,format)
            assert_array_equal(c.todense(), D)

    def test_tobsr(self):
        x = array([[1,0,2,0],[0,0,0,0],[0,0,4,5]])
        y = array([[0,1,2],[3,0,5]])
        A = kron(x,y)
        Asp = self.spmatrix(A)
        for format in ['bsr']:
            fn = getattr(Asp, 'to' + format)

            for X in [1, 2, 3, 6]:
                for Y in [1, 2, 3, 4, 6, 12]:
                    assert_equal(fn(blocksize=(X,Y)).todense(), A)

    def test_transpose(self):
        dat_1 = self.dat
        dat_2 = np.array([[]])
        matrices = [dat_1, dat_2]

        def check(dtype, j):
            dat = np.matrix(matrices[j], dtype=dtype)
            datsp = self.spmatrix(dat)

            a = datsp.transpose()
            b = dat.transpose()
            assert_array_equal(a.todense(), b)
            assert_array_equal(a.transpose().todense(), dat)
            assert_equal(a.dtype, b.dtype)

            assert_array_equal(self.spmatrix((3,4)).T.todense(), zeros((4,3)))

        for dtype in self.checked_dtypes:
            for j in range(len(matrices)):
                yield check, dtype, j

    def test_add_dense(self):
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            # adding a dense matrix to a sparse matrix
            sum1 = dat + datsp
            assert_array_equal(sum1, dat + dat)
            sum2 = datsp + dat
            assert_array_equal(sum2, dat + dat)

        for dtype in self.checked_dtypes:
            yield check, dtype

    def test_sub_dense(self):
        # subtracting a dense matrix to/from a sparse matrix
        def check(dtype):
            dat = self.dat_dtypes[dtype]
            datsp = self.datsp_dtypes[dtype]

            # Behavior is different for bool.
            if dat.dtype == bool:
                sum1 = dat - datsp
                assert_array_equal(sum1, dat - dat)
                sum2 = datsp - dat
                assert_array_equal(sum2, dat - dat)
            else:
                # Manually add to avoid upcasting from scalar
                # multiplication.
                sum1 = (dat + dat + dat) - datsp
                assert_array_equal(sum1, dat + dat)
                sum2 = (datsp + datsp + datsp) - dat
                assert_array_equal(sum2, dat + dat)

        for dtype in self.checked_dtypes:
            if (dtype == np.dtype('bool')) and (
                    NumpyVersion(np.__version__) >= '1.9.0.dev'):
                # boolean array subtraction deprecated in 1.9.0
                continue

            yield check, dtype

    def test_maximum_minimum(self):
        A_dense = np.array([[1, 0, 3], [0, 4, 5], [0, 0, 0]])
        B_dense = np.array([[1, 1, 2], [0, 3, 6], [1, -1, 0]])

        A_dense_cpx = np.array([[1, 0, 3], [0, 4+2j, 5], [0, 1j, -1j]])

        def check(dtype, dtype2, btype):
            if np.issubdtype(dtype, np.complexfloating):
                A = self.spmatrix(A_dense_cpx.astype(dtype))
            else:
                A = self.spmatrix(A_dense.astype(dtype))
            if btype == 'scalar':
                B = dtype2.type(1)
            elif btype == 'scalar2':
                B = dtype2.type(-1)
            elif btype == 'dense':
                B = B_dense.astype(dtype2)
            elif btype == 'sparse':
                B = self.spmatrix(B_dense.astype(dtype2))
            else:
                raise ValueError()

            max_s = A.maximum(B)
            max_d = np.maximum(todense(A), todense(B))
            assert_array_equal(todense(max_s), max_d)
            assert_equal(max_s.dtype, max_d.dtype)

            min_s = A.minimum(B)
            min_d = np.minimum(todense(A), todense(B))
            assert_array_equal(todense(min_s), min_d)
            assert_equal(min_s.dtype, min_d.dtype)

        for dtype in self.checked_dtypes:
            for dtype2 in [np.int8, np.float_, np.complex_]:
                for btype in ['scalar', 'scalar2', 'dense', 'sparse']:
                    yield check, np.dtype(dtype), np.dtype(dtype2), btype

    def test_copy(self):
        # Check whether the copy=True and copy=False keywords work
        A = self.datsp

        # check that copy preserves format
        assert_equal(A.copy().format, A.format)
        assert_equal(A.__class__(A,copy=True).format, A.format)
        assert_equal(A.__class__(A,copy=False).format, A.format)

        assert_equal(A.copy().todense(), A.todense())
        assert_equal(A.__class__(A,copy=True).todense(), A.todense())
        assert_equal(A.__class__(A,copy=False).todense(), A.todense())

        # check that XXX_matrix.toXXX() works
        toself = getattr(A,'to' + A.format)
        assert_equal(toself().format, A.format)
        assert_equal(toself(copy=True).format, A.format)
        assert_equal(toself(copy=False).format, A.format)

        assert_equal(toself().todense(), A.todense())
        assert_equal(toself(copy=True).todense(), A.todense())
        assert_equal(toself(copy=False).todense(), A.todense())

        # check whether the data is copied?
        # TODO: deal with non-indexable types somehow
        B = A.copy()
        try:
            B[0,0] += 1
            assert_(B[0,0] != A[0,0])
        except NotImplementedError:
            # not all sparse matrices can be indexed
            pass
        except TypeError:
            # not all sparse matrices can be indexed
            pass

    # test that __iter__ is compatible with NumPy matrix
    def test_iterator(self):
        B = np.matrix(np.arange(50).reshape(5, 10))
        A = self.spmatrix(B)

        for x, y in zip(A, B):
            assert_equal(x.todense(), y)

    def test_size_zero_matrix_arithmetic(self):
        # Test basic matrix arithmatic with shapes like (0,0), (10,0),
        # (0, 3), etc.
        mat = np.matrix([])
        a = mat.reshape((0, 0))
        b = mat.reshape((0, 1))
        c = mat.reshape((0, 5))
        d = mat.reshape((1, 0))
        e = mat.reshape((5, 0))
        f = np.matrix(np.ones([5, 5]))

        asp = self.spmatrix(a)
        bsp = self.spmatrix(b)
        csp = self.spmatrix(c)
        dsp = self.spmatrix(d)
        esp = self.spmatrix(e)
        fsp = self.spmatrix(f)

        # matrix product.
        assert_array_equal(asp.dot(asp).A, np.dot(a, a).A)
        assert_array_equal(bsp.dot(dsp).A, np.dot(b, d).A)
        assert_array_equal(dsp.dot(bsp).A, np.dot(d, b).A)
        assert_array_equal(csp.dot(esp).A, np.dot(c, e).A)
        assert_array_equal(csp.dot(fsp).A, np.dot(c, f).A)
        assert_array_equal(esp.dot(csp).A, np.dot(e, c).A)
        assert_array_equal(dsp.dot(csp).A, np.dot(d, c).A)
        assert_array_equal(fsp.dot(esp).A, np.dot(f, e).A)

        # bad matrix products
        assert_raises(ValueError, dsp.dot, e)
        assert_raises(ValueError, asp.dot, d)

        # elemente-wise multiplication
        assert_array_equal(asp.multiply(asp).A, np.multiply(a, a).A)
        assert_array_equal(bsp.multiply(bsp).A, np.multiply(b, b).A)
        assert_array_equal(dsp.multiply(dsp).A, np.multiply(d, d).A)

        assert_array_equal(asp.multiply(a).A, np.multiply(a, a).A)
        assert_array_equal(bsp.multiply(b).A, np.multiply(b, b).A)
        assert_array_equal(dsp.multiply(d).A, np.multiply(d, d).A)

        assert_array_equal(asp.multiply(6).A, np.multiply(a, 6).A)
        assert_array_equal(bsp.multiply(6).A, np.multiply(b, 6).A)
        assert_array_equal(dsp.multiply(6).A, np.multiply(d, 6).A)

        # bad element-wise multiplication
        assert_raises(ValueError, asp.multiply, c)
        assert_raises(ValueError, esp.multiply, c)

        # Addition
        assert_array_equal(asp.__add__(asp).A, a.__add__(a).A)
        assert_array_equal(bsp.__add__(bsp).A, b.__add__(b).A)
        assert_array_equal(dsp.__add__(dsp).A, d.__add__(d).A)

        # bad addition
        assert_raises(ValueError, asp.__add__, dsp)
        assert_raises(ValueError, bsp.__add__, asp)

    def test_size_zero_conversions(self):
        mat = np.matrix([])
        a = mat.reshape((0, 0))
        b = mat.reshape((0, 5))
        c = mat.reshape((5, 0))

        for m in [a, b, c]:
            spm = self.spmatrix(m)
            assert_array_equal(spm.tocoo().A, m)
            assert_array_equal(spm.tocsr().A, m)
            assert_array_equal(spm.tocsc().A, m)
            assert_array_equal(spm.tolil().A, m)
            assert_array_equal(spm.todok().A, m)
            assert_array_equal(spm.tobsr().A, m)

    def test_unary_ufunc_overrides(self):
        def check(name):
            if not HAS_NUMPY_UFUNC:
                if name == "sign":
                    raise nose.SkipTest("sign conflicts with comparison op "
                                        "support on Numpy without __numpy_ufunc__")
                if self.spmatrix in (dok_matrix, lil_matrix):
                    raise nose.SkipTest("Unary ops not implemented for dok/lil "
                                        "with Numpy without __numpy_ufunc__")
            ufunc = getattr(np, name)

            X = self.spmatrix(np.arange(20).reshape(4, 5) / 20.)
            X0 = ufunc(X.toarray())

            X2 = ufunc(X)
            assert_array_equal(X2.toarray(), X0)

            if HAS_NUMPY_UFUNC:
                # the out argument doesn't work on Numpy without __numpy_ufunc__
                out = np.zeros_like(X0)
                X3 = ufunc(X, out=out)
                assert_(X3 is out)
                assert_array_equal(todense(X3), ufunc(todense(X)))

                out = csc_matrix(out.shape, dtype=out.dtype)
                out[:,1] = 999
                X4 = ufunc(X, out=out)
                assert_(X4 is out)
                assert_array_equal(todense(X4), ufunc(todense(X)))

        for name in ["sin", "tan", "arcsin", "arctan", "sinh", "tanh",
                     "arcsinh", "arctanh", "rint", "sign", "expm1", "log1p",
                     "deg2rad", "rad2deg", "floor", "ceil", "trunc", "sqrt",
                     "abs"]:
            yield check, name

    def test_binary_ufunc_overrides(self):
        # data
        a = np.array([[1, 2, 3],
                      [4, 5, 0],
                      [7, 8, 9]])
        b = np.array([[9, 8, 7],
                      [6, 0, 0],
                      [3, 2, 1]])
        c = 1.0
        d = 1 + 2j
        e = 5

        asp = self.spmatrix(a)
        bsp = self.spmatrix(b)

        a_items = dict(dense=a, scalar=c, cplx_scalar=d, int_scalar=e, sparse=asp)
        b_items = dict(dense=b, scalar=c, cplx_scalar=d, int_scalar=e, sparse=bsp)

        @dec.skipif(not HAS_NUMPY_UFUNC, "feature requires Numpy with __numpy_ufunc__")
        def check(i, j, dtype):
            ax = a_items[i]
            bx = b_items[j]

            if issparse(ax):
                ax = ax.astype(dtype)
            if issparse(bx):
                bx = bx.astype(dtype)

            a = todense(ax)
            b = todense(bx)

            def check_one(ufunc, allclose=False):
                # without out argument
                expected = ufunc(a, b)
                got = ufunc(ax, bx)
                if allclose:
                    assert_allclose(todense(got), expected,
                                    rtol=5e-15, atol=0)
                else:
                    assert_array_equal(todense(got), expected)

                # with out argument
                out = np.zeros(got.shape, dtype=got.dtype)
                out.fill(np.nan)
                got = ufunc(ax, bx, out=out)
                assert_(got is out)
                if allclose:
                    assert_allclose(todense(got), expected,
                                    rtol=5e-15, atol=0)
                else:
                    assert_array_equal(todense(got), expected)

                out = csr_matrix(got.shape, dtype=out.dtype)
                out[0,:] = 999
                got = ufunc(ax, bx, out=out)
                assert_(got is out)
                if allclose:
                    assert_allclose(todense(got), expected,
                                    rtol=5e-15, atol=0)
                else:
                    assert_array_equal(todense(got), expected)

            # -- associative

            # multiply
            check_one(np.multiply)

            # add
            if isscalarlike(ax) or isscalarlike(bx):
                try:
                    check_one(np.add)
                except NotImplementedError:
                    # Not implemented for all spmatrix types
                    pass
            else:
                check_one(np.add)

            # maximum
            check_one(np.maximum)

            # minimum
            check_one(np.minimum)

            # -- non-associative

            # dot
            check_one(np.dot)

            # subtract
            if isscalarlike(ax) or isscalarlike(bx):
                try:
                    check_one(np.subtract)
                except NotImplementedError:
                    # Not implemented for all spmatrix types
                    pass
            else:
                check_one(np.subtract)

            # divide
            with np.errstate(divide='ignore', invalid='ignore'):
                if isscalarlike(bx):
                    # Rounding error may be different, as the sparse implementation
                    # computes a/b -> a * (1/b) if b is a scalar
                    check_one(np.divide, allclose=True)
                else:
                    check_one(np.divide)

                # true_divide
                if isscalarlike(bx):
                    check_one(np.true_divide, allclose=True)
                else:
                    check_one(np.true_divide)

        for i in a_items.keys():
            for j in b_items.keys():
                for dtype in [np.int_, np.float_, np.complex_]:
                    if i == 'sparse' or j == 'sparse':
                        yield check, i, j, dtype

    @dec.skipif(not HAS_NUMPY_UFUNC, "feature requires Numpy with __numpy_ufunc__")
    def test_ufunc_object_array(self):
        # This tests compatibility with previous Numpy object array
        # ufunc behavior. See gh-3345.
        a = self.spmatrix([[1, 2]])
        b = self.spmatrix([[3], [4]])
        c = self.spmatrix([[5], [6]])

        # Should distribute the operation across the object array
        d = np.multiply(a, np.array([[b], [c]]))
        assert_(d.dtype == np.object_)
        assert_(d.shape == (2, 1))
        assert_allclose(d[0,0].A, (a*b).A)
        assert_allclose(d[1,0].A, (a*c).A)

        # Lists also get cast to object arrays
        d = np.multiply(a, [[b], [c]])
        assert_(d.dtype == np.object_)
        assert_(d.shape == (2, 1))
        assert_allclose(d[0,0].A, (a*b).A)
        assert_allclose(d[1,0].A, (a*c).A)

        # This returned NotImplemented in Numpy < 1.9; do it properly now
        d = np.multiply(np.array([[b], [c]]), a)
        assert_(d.dtype == np.object_)
        assert_(d.shape == (2, 1))
        assert_allclose(d[0,0].A, (b*a).A)
        assert_allclose(d[1,0].A, (c*a).A)

        d = np.subtract(np.array(b, dtype=object), c)
        assert_(isinstance(d, sparse.spmatrix))
        assert_allclose(d.A, (b - c).A)
