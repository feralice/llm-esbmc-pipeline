# Draft issue for ESBMC (not posted)

Reproducer: `42_tupla_de_str_retorno_min.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] Unpacking a `tuple[str, str]` return with a nondet_str() aborts (Incompatible struct in cast-to-struct)

### Reproducer
```python
def pair() -> tuple[str, str]:
    return ("x", nondet_str())


a, b = pair()
assert a == "x"
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
The program runs without error in CPython. Expected `VERIFICATION SUCCESSFUL`.

### Actual
Exit code 134, while encoding the claim of the `assert` (`(signed int)(a[0]) == 120 && (signed int)(a[1]) == 0`):
```
ERROR: Incompatible struct in cast-to-struct
```
Without the `assert` the result is `VERIFICATION SUCCESSFUL`. The original program (both elements from
`nondet_str()`, then `if scheme == "bearer": raise ValueError`) aborts the same way while encoding the
unwinding claim of `strcmp`; CPython raises `ValueError` there when the first string is `"bearer"`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
