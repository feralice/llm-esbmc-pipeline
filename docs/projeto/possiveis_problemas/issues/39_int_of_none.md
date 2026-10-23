# Draft issue for ESBMC (not posted)

Reproducer: `39_int_de_none_min.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `int(None)` does not raise TypeError

### Reproducer
```python
from typing import Optional

status: Optional[str] = None
code = int(status)
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`.
Expected `VERIFICATION FAILED` with `TypeError`.

### Actual
`Generated 0 VCC(s)` and `VERIFICATION SUCCESSFUL`. Same result when `status` is set to `"7"` on one path.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
