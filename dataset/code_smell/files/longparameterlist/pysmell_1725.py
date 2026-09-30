# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/scipy/scipy/blob/v0.16.0b2/scipy/optimize/optimize.py#L621-L667
# smelly line(s) in the original file: 621
# smelly line(s) in this file: 8
# ids: pysmell_1725
# note: Python 2 era source, kept as found
def check_grad(func, grad, x0, *args, **kwargs):
    """Check the correctness of a gradient function by comparing it against a
    (forward) finite-difference approximation of the gradient.

    Parameters
    ----------
    func : callable ``func(x0, *args)``
        Function whose derivative is to be checked.
    grad : callable ``grad(x0, *args)``
        Gradient of `func`.
    x0 : ndarray
        Points to check `grad` against forward difference approximation of grad
        using `func`.
    args : \*args, optional
        Extra arguments passed to `func` and `grad`.
    epsilon : float, optional
        Step size used for the finite difference approximation. It defaults to
        ``sqrt(numpy.finfo(float).eps)``, which is approximately 1.49e-08.

    Returns
    -------
    err : float
        The square root of the sum of squares (i.e. the 2-norm) of the
        difference between ``grad(x0, *args)`` and the finite difference
        approximation of `grad` using func at the points `x0`.

    See Also
    --------
    approx_fprime

    Examples
    --------
    >>> def func(x):
    ...     return x[0]**2 - 0.5 * x[1]**3
    >>> def grad(x):
    ...     return [2 * x[0], -1.5 * x[1]**2]
    >>> from scipy.optimize import check_grad
    >>> check_grad(func, grad, [1.5, -1.5])
    2.9802322387695312e-08

    """
    step = kwargs.pop('epsilon', _epsilon)
    if kwargs:
        raise ValueError("Unknown keyword arguments: %r" %
                         (list(kwargs.keys()),))
    return sqrt(sum((grad(x0, *args) -
                     approx_fprime(x0, func, step, *args))**2))
