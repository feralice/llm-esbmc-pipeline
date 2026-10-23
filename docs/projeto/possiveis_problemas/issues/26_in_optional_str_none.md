# Draft issue for ESBMC (not posted)

Reproducer: `26_in_str_none_min.py (also 18_for_lista_global_in_none_min.py)`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `x in s` with `s: Optional[str]` equal to None does not raise TypeError

### Summary
Membership on a `None` value typed `Optional[str]` never raises `TypeError`. As a local variable it is
proved safe; as a parameter it only fails on an unwinding assertion inside `strstr`. #8249 fixed the same
construct for `Optional[dict]` and `Optional[list]`, not for `str`.

### Reproducer
```python
from typing import Optional

s: Optional[str] = None
found = "ab" in s
```

Same construct through a parameter:
```python
from typing import Optional


def match(stderr: Optional[str]) -> bool:
    return 'ab' in stderr


match(None)
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `TypeError: argument of type 'NoneType' is not iterable`. Expected `VERIFICATION FAILED` with
`TypeError`.

### Actual
First program: `Generated 0 VCC(s)` and `VERIFICATION SUCCESSFUL`.

Second program, only an unwinding assertion in the C model (same with `--unwind 30`):
```
Violated property:
  file /esbmc-vfs/libc/library/string.c line 245 column 3 function strstr
  unwinding assertion loop 2
VERIFICATION FAILED
```

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
