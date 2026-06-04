def quantile(ngroups: int, q_len: int, result_len: int) -> None:
    indices_len = ngroups * q_len
    assert indices_len == result_len
