# Draft issue for ESBMC (not posted)

Reproducer: `40_sequence_indice.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] Indexing a `Sequence[str]` parameter out of range is not checked

### Reproducer
```python
from typing import Sequence


def second(xs: Sequence[str]) -> str:
    return xs[1]


def main() -> None:
    second(["a"])


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `IndexError: list index out of range`. Expected `VERIFICATION FAILED` with `IndexError`.

### Actual
`Generated 0 VCC(s)` and `VERIFICATION SUCCESSFUL`. With `xs: list[str]` the result is `FAILED` with
`IndexError`. A module-level `xs: Sequence[str] = ["a"]` is refused with `NameError: name 'Sequence' is not defined`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
