TYPE_MAX: int = 255  # stand-in for remerkleable's UINT64_MAX = 2**64 - 1;
# the literal 2**64 - 1 itself overflows ESBMC-Python's fixed-width int
# representation (see esbmc-python-guide), so the bound-check mechanism is
# reproduced at a smaller scale, same technique io_real_01 uses for int8.


def integer_squareroot_first_step(x: int) -> int:
    # Real code (ethereum/consensus-specs, specs/phase0/beacon-chain.md,
    # integer_squareroot, fixed by PR #3600): `y = (x + 1) // 2` computes
    # x + 1 on a remerkleable.uint64 value unconditionally. remerkleable's
    # uint64 bounds-checks every arithmetic result to [0, 2**64) and raises
    # ValueError instead of wrapping, so x == 2**64 - 1 (UINT64_MAX) makes
    # x + 1 itself raise ValueError before the while-loop below even runs.
    # Confirmed by the eth2spec maintainers; fixed by special-casing
    # n == UINT64_MAX before this line.
    assert x != TYPE_MAX
    return x + 1


def main() -> None:
    x: int = nondet_int()
    __ESBMC_assume(x >= 0 and x <= TYPE_MAX)
    integer_squareroot_first_step(x)


main()
