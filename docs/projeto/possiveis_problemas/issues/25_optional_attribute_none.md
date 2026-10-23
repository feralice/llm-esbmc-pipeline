# Draft issue for ESBMC (not posted)

Reproducer: `25_atributo_em_none.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] Attribute read on an Optional attribute that may be None is proved safe

### Summary
#8325 (fixed by #8756) makes an attribute read on `None` raise `AttributeError`. When the `None` value
comes from an `Optional[...]` attribute that is set on only one path, the `AttributeError` properties are
generated but proved unreachable.

### Reproducer
```python
from typing import Optional


class Node:
    def __init__(self) -> None:
        self.nxt: Optional[Node] = None
        self.val: int = 0


a = Node()
if nondet_bool():
    a.nxt = Node()
x = a.nxt.val
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython, when `nondet_bool()` is false: `AttributeError: 'NoneType' object has no attribute 'val'`.
Expected `VERIFICATION FAILED` with `AttributeError`.

### Actual
```
  PASSED       [global.assertion.3]  line 12  uncaught exception: AttributeError
  PASSED       [global.assertion.4]  line 13  uncaught exception: AttributeError
VERIFICATION SUCCESSFUL
```
Without `--no-pointer-check` the result is `FAILED` on `dereference failure: NULL pointer`, still without
`AttributeError`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
