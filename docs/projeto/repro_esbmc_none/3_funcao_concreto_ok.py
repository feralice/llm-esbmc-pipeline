from typing import Optional

def f(s: int) -> Optional[str]:
    if s == 200:
        return "OK"
    return None

r: Optional[str] = f(999)
assert r is not None
