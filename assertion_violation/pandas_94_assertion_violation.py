def take(is_period_dtype: bool, taken_freq: int, self_freq: int) -> None:
    freq = self_freq if is_period_dtype else 0
    assert taken_freq == freq
