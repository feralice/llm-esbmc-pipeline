def scale_total(total_is_none: bool, total_val: float, unit_scale: float) -> float:
    # Real code (tqdm/_tqdm.py:320, tqdm.__init__): `total *= unit_scale`
    # runs whenever `unit_scale not in (True, 1)` (a real numeric scale
    # factor was passed), even if total is None -- tqdm's default when the
    # wrapped iterable exposes no length. None *= float raises TypeError.
    assert not total_is_none
    result: float = 0.0
    if not total_is_none:
        result = total_val * unit_scale
    return result


def main() -> None:
    total_is_none: bool = nondet_bool()
    total_val: float = nondet_float()
    unit_scale: float = nondet_float()
    __ESBMC_assume(unit_scale == unit_scale)
    # Real precondition: caller already filtered out unit_scale in (True, 1)
    # before this line runs.
    __ESBMC_assume(unit_scale != 1.0)
    scale_total(total_is_none, total_val, unit_scale)


main()
