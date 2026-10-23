# Draft issue for ESBMC (not posted)

Reproducer: `29_optional_dict_como_valor.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `dict[str, Optional[dict[str, str]]]` attribute aborts the solver (Z3 sort error, Bitwuzla SIGSEGV)

### Reproducer
```python
from typing import Optional


class Markdown:
    def __init__(self) -> None:
        extras: dict[str, Optional[dict[str, str]]] = {}
        inner: Optional[dict[str, str]] = None
        if nondet_bool():
            d: dict[str, str] = {}
            inner = d
        extras["k"] = inner
        self.extras: dict[str, Optional[dict[str, str]]] = extras

    def lookup(self) -> None:
        h = self.extras["k"]
        if "t" in h:
            pass


def main() -> None:
    Markdown().lookup()


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`, with Z3 (default) and
with `--bitwuzla`.

### Expected
CPython, when `nondet_bool()` is false: `TypeError: argument of type 'NoneType' is not iterable`.
Expected `VERIFICATION FAILED` with `TypeError`.

### Actual
Z3 (exit code 134):
```
ERROR: Z3 error Sorts |struct_type_tag-Optional_struct ...
```
Bitwuzla 0.9.0 (exit code 139), while encoding the unwinding claim of `__ESBMC_list_contains`:
```
ESBMC caught SIGSEGV: this is an internal error, not a verification result.
```
A version without the class, building the same dict at module level, aborts with
`uncaught exception [St19bad_optional_access]: bad optional access` instead.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
