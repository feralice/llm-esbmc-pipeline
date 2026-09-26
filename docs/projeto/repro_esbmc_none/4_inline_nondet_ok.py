from typing import Optional

s: int = nondet_int()
r: Optional[str] = None
if s == 200:
    r = "OK"
assert r is not None
