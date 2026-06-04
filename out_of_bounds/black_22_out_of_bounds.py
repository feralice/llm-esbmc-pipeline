STANDALONE_COMMENT = 54


def is_comment(leaves_len: int, first_leaf_type: int) -> bool:
    _leaves = [None] * leaves_len
    _ = _leaves[0]
    return first_leaf_type == STANDALONE_COMMENT
