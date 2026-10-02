def string_to_int(
    string,
    alphabet,
    alphabet_index=None,
):
    """
    Convert a string to a number, using the given alphabet.

    The input is assumed to have the most significant digit first.

    The alphabet_index, if provided, should map each character to its index:
    ``{char: idx for idx, char in enumerate(alphabet)}``. This avoids rebuilding
    the index on each call when decoding multiple strings with the same alphabet.
    If this is passed, `alphabet` is ignored.
    """
    if alphabet_index is None:
        alphabet_index = {char: idx for idx, char in enumerate(alphabet)}
    number = 0
    alpha_len = len(alphabet)
    for char in string:
        try:
            number = number * alpha_len + alphabet_index[char]
        except KeyError:
            raise ValueError("'{}' is not in alphabet".format(char))
    return number
