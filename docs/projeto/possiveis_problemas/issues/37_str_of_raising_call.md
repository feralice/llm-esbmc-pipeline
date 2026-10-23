# Draft issue for ESBMC (not posted)

Reproducer: `37_str_de_chamada_min.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] An exception raised inside `str(f())` is lost

### Reproducer
```python
def label() -> str:
    raise ValueError("x")


s = str(label())
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `ValueError: x`. Expected `VERIFICATION FAILED` with `ValueError`.

### Actual
`Generated 0 VCC(s)` and `VERIFICATION SUCCESSFUL`. Without the `str()` wrapper (`s = label()`) the
result is `FAILED` with `ValueError`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
