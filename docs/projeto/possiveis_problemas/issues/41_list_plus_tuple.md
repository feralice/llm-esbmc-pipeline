# Draft issue for ESBMC (not posted)

Reproducer: `41_lista_mais_tupla_min.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `list + tuple` does not raise TypeError

### Reproducer
```python
x = [1] + (2, 3)
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `TypeError: can only concatenate list (not "tuple") to list`. Expected `VERIFICATION FAILED` with
`TypeError`.

### Actual
`Generated 0 VCC(s)` and `VERIFICATION SUCCESSFUL`. With a tuple parameter followed by `len(x)`, ESBMC
aborts with `Unexpected type in int/ptr typecast`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
