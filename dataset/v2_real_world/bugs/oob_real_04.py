def buggy_realise(cached: list) -> int:
    # Real code (thefuck/types.py, SortedCorrectedCommandsSequence._realise,
    # BugsInPy thefuck bug #22): indexes self._cached[0] unconditionally,
    # raising IndexError when the generator produced zero corrected commands.
    return cached[0]


def main() -> None:
    cached: list = []
    buggy_realise(cached)


main()
