def flat_matrix_get(flat: list[int], row: int, col: int, num_cols: int) -> int:
    idx = row * num_cols + col
    return flat[idx]
