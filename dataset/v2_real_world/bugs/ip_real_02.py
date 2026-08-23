def buggy_raises(make_current_requested: bool, current_is_none: bool) -> bool:
    # Real code (tornado/ioloop.py:IOLoop.__init__, BugsInPy tornado #14):
    # `elif make_current: if IOLoop.current(instance=False) is None: raise
    # RuntimeError("current IOLoop already exists")`. Inverted condition:
    # raises when there is NO current loop, the opposite of the intended
    # guard against clobbering an existing one.
    if make_current_requested:
        return current_is_none
    return False


def correct_raises(make_current_requested: bool, current_is_none: bool) -> bool:
    if make_current_requested:
        return not current_is_none
    return False


def main() -> None:
    current_is_none: bool = nondet_bool()
    b: bool = buggy_raises(True, current_is_none)
    c: bool = correct_raises(True, current_is_none)
    assert b == c


main()
