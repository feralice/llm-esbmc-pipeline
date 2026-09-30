# smell: LongScopeChaining
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/sparse/tests/test_base.py#L1597-L1714
# smelly line(s) in the original file: 1597
# smelly line(s) in this file: 8
# ids: pysmell_2009
# note: Python 2 era source, kept as found
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
