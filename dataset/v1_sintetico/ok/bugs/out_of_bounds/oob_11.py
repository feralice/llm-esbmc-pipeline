def strided_fetch(data: list[int], base: int, stride: int, steps: int) -> int:
    idx = base + stride * steps
    return data[idx]
