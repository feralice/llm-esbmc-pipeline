import math


def compute_len_buggy(end_index: int, start_index: int, batch_size: int, stride: int) -> int:
    return math.ceil((end_index - start_index) / (batch_size * stride))


def compute_len_fixed(end_index: int, start_index: int, batch_size: int, stride: int) -> int:
    return math.ceil((end_index - start_index + 1) / (batch_size * stride))


def main() -> None:
    end_index: int = 10
    start_index: int = 0
    batch_size: int = 5
    stride: int = 1
    buggy: int = compute_len_buggy(end_index, start_index, batch_size, stride)
    correct: int = compute_len_fixed(end_index, start_index, batch_size, stride)
    assert buggy == correct


main()
