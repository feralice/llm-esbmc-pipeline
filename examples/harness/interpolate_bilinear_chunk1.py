import math


def interpolate_bilinear_trip_count(h_src: int, chunk_size: int) -> int:
    wdw_size = chunk_size
    step_size = wdw_size - 1
    return math.ceil((h_src - wdw_size) / step_size) + 1


def main() -> int:
    return interpolate_bilinear_trip_count(5, 1)


main()
