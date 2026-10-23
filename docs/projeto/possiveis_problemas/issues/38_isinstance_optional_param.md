# Draft issue for ESBMC (not posted)

Reproducer: `38_not_isinstance_optional.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `isinstance(x, str)` on an `Optional[str]` parameter that may be None is always true

### Reproducer
```python
from typing import Optional


def check(text: Optional[str]) -> str:
    if not isinstance(text, str):
        raise TypeError("not a string")
    return text


def main() -> None:
    text: Optional[str] = None
    if nondet_bool():
        text = "a"
    check(text)


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython, when `nondet_bool()` is false: `TypeError: not a string`. Expected `VERIFICATION FAILED` with
`TypeError`.

### Actual
```
  PASSED       [check.assertion.1]   line 8  uncaught exception: TypeError
VERIFICATION SUCCESSFUL
```
`check(None)` gives `FAILED` with `TypeError`, as does the same test on a local variable. The `None` is lost
only when a value that may be `None` on one path is passed as an argument.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
