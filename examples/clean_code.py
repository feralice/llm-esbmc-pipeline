"""Cenário: código limpo sem bugs nem smells — espera findings vazio ou low confidence."""
from typing import List


def sum_positive(values: List[int]) -> int:
    return sum(v for v in values if v > 0)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def is_palindrome(text: str) -> bool:
    cleaned = text.lower().replace(" ", "")
    return cleaned == "".join(reversed(cleaned))
