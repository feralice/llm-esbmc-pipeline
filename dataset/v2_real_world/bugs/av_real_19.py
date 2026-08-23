def make_interval_buggy(vmin: float, vmax: float, oldmin: float, oldmax: float) -> float:
    return max(vmin, vmax, oldmax)


def make_interval_fixed(vmin: float, vmax: float, oldmin: float, oldmax: float) -> float:
    return max(vmin, vmax, oldmin)


def main() -> None:
    vmin: float = 1.0
    vmax: float = 2.0
    oldmin: float = 0.5
    oldmax: float = 5.0
    buggy: float = make_interval_buggy(vmin, vmax, oldmin, oldmax)
    correct: float = make_interval_fixed(vmin, vmax, oldmin, oldmax)
    assert buggy == correct


main()
