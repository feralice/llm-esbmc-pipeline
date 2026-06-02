def compare_interval_dtype(left_is_interval: bool, right_is_interval: bool) -> bool:
    if left_is_interval or right_is_interval:
        assert left_is_interval and right_is_interval
        return True

    return False