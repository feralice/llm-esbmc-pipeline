def scaled_index_lookup(data: list[int], pos: int, scale: int, bias: int) -> int:
    idx = pos * scale + bias
    return data[idx]
