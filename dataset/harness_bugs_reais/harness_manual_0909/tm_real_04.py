def str_to_int_guard(is_str: bool) -> bool:
    # Real code (youtube_dl/utils.py:3519-3524, str_to_int): pre-fix only
    # guarded `if int_str is None: return None`, so a non-None, non-string
    # argument (already an int) fell through to string-only operations
    # (re.sub / .replace-style cleanup) and crashed with AttributeError:
    # 'int' object has no attribute 'replace'. Fixed to
    # `if not isinstance(int_str, compat_str): return int_str`.
    assert is_str
    return is_str


def main() -> None:
    is_str: bool = nondet_bool()
    str_to_int_guard(is_str)


main()
