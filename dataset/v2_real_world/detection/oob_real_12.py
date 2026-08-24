def fast_float(
    x: str,
    key: Callable[[str], str] = lambda x: x,
    nan: float = float("inf"),
    _uni: Callable[[str, StrOrFloat], StrOrFloat] = unicodedata.numeric,
    _nan_inf: frozenset[str] = NAN_INF,
    _first_char: frozenset[str] = POTENTIAL_FIRST_CHAR,
) -> StrOrFloat:
    """
    Convert a string to a float quickly, return input as-is if not possible.

    We don't need to accept all input that the real fast_int accepts because
    natsort is controlling what is passed to this function.

    Parameters
    ----------
    x : str
        String to attempt to convert to a float.
    key : callable
        Single-argument function to apply to *x* if conversion fails.
    nan : float
        Value to return instead of NaN if NaN would be returned.

    Returns
    -------
    *str* or *float*

    """
    if x[0] in _first_char or x.lstrip()[:3] in _nan_inf:
        try:
            ret = float(x)
        except ValueError:
            try:
                return _uni(x, key(x)) if len(x) == 1 else key(x)
            except TypeError:  # pragma: no cover
                return key(x)
        else:
            return nan if ret != ret else ret
    else:
        try:
            return _uni(x, key(x)) if len(x) == 1 else key(x)
        except TypeError:  # pragma: no cover
            return key(x)
