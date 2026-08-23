def realise_first(cached: list) -> int:
    # Real code (thefuck/types.py:SortedCorrectedCommandsSequence._realise,
    # BugsInPy thefuck bug #22): `self._cached[0]` is indexed unconditionally
    # after the generator is realised, but `_cached` can be empty (e.g. no
    # corrected commands were produced) -- the fix guards the whole realise
    # step behind `if self._cached:`.
    return cached[0]


def main() -> None:
    cached: list = []
    realise_first(cached)


main()
