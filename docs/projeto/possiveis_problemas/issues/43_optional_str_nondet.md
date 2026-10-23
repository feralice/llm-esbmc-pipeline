# Draft issue for ESBMC (not posted)

Reproducer: `43_optional_str_nondet.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `Optional[str]` assigned `nondet_str()` on one path: `is not None` folds to true

### Reproducer
```python
from typing import Optional


def main() -> None:
    text: Optional[str] = None
    if nondet_bool():
        text = nondet_str()
    assert text is not None


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython, when `nondet_bool()` is false: `AssertionError`. Expected `VERIFICATION FAILED`.

### Actual
```
  PASSED       [main.assertion.1]  line 11  assertion !(ISNONE(text, 0))
VERIFICATION SUCCESSFUL
```
With `text = "a"` instead of `nondet_str()`, or with `Optional[int]` and `nondet_int()`, the result is
`FAILED`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
