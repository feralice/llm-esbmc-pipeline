"""Cenário: operações protegidas por guardas — LLM NÃO deve reportar como verifiable=true."""
from typing import List


def safe_divide(a: int, b: int) -> float:
    if b == 0:
        return 0.0
    return a / b


def safe_get(items: List[int], index: int) -> int:
    if not items or index < 0 or index >= len(items):
        return -1
    return items[index]


def safe_modulo(x: int, mod: int) -> int:
    assert mod != 0, "mod must be non-zero"
    return x % mod
