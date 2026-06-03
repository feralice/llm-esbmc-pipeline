"""Small ESBMC Python stubs used by generated verification drivers.

The ESBMC Python frontend recognizes these helper names during formal
verification. The fallback implementations below also let instrumented files run
under CPython for smoke tests and debugging.
"""
from __future__ import annotations

import random


def nondet_int() -> int:
    return random.randint(-(2**31), 2**31 - 1)


def nondet_bool() -> bool:
    return bool(random.randint(0, 1))


def nondet_float() -> float:
    return random.uniform(-1_000_000.0, 1_000_000.0)


def __ESBMC_assume(cond: bool) -> None:
    if not cond:
        raise AssertionError("ESBMC assumption violated")


def __ESBMC_assert(cond: bool, msg: str = "") -> None:
    assert cond, msg
