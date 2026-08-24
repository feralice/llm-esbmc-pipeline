def buggy_filled(fillstyle_is_none: bool) -> bool:
    # Real code (lib/matplotlib/markers.py:MarkerStyle.__init__, BugsInPy
    # matplotlib bug #3): `self._filled = True` was hardcoded, instead of
    # being derived from the fillstyle, so an unfilled marker
    # (fillstyle == 'none') was wrongly reported as filled.
    return True


def correct_filled(fillstyle_is_none: bool) -> bool:
    # Fix: derive from whether fillstyle equals 'none'.
    return not fillstyle_is_none


def main() -> None:
    fillstyle_is_none: bool = nondet_bool()
    buggy: bool = buggy_filled(fillstyle_is_none)
    correct: bool = correct_filled(fillstyle_is_none)
    assert buggy == correct


main()
