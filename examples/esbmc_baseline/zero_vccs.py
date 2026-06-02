"""Expected: no_violation_found + zero_vccs=True — only function definitions, no top-level calls.

This file documents the known limitation: ESBMC Flow A requires top-level calls
to generate VCCs. Function-only files always produce 0 VCCs and VERIFICATION SUCCESSFUL,
which is not the same as "proven safe".
"""
from typing import List


def risky_divide(a: int, b: int) -> int:
    return a // b


def risky_get(items: List[int], index: int) -> int:
    return items[index]
