def _type(string):
    "The least generic type (int, float, str, unicode)."
    if _isint(string):
        return int
    elif _isnumber(string):
        return float
    elif isinstance(string, _binary_type):
        return _binary_type
    else:
        return _text_type
