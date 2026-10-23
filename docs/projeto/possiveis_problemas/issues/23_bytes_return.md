# Draft issue for ESBMC (not posted)

Reproducer: `23_bytes_literal_min.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] A function returning a bytes literal is refused (cannot determine the length of a `-> bytes` return value)

### Summary
A `-> bytes` function that returns a literal is refused. ESBMC 8.5.0 accepted it and reported the
out-of-bounds read; the refusal appeared after #7902.

### Reproducer
```python
def encode() -> bytes:
    return b"ab"


x = encode()[2]
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `IndexError: index out of range`. Expected `VERIFICATION FAILED` with `IndexError`.

### Actual
```
ERROR: cannot determine the length of a `-> bytes` return value for 'encode'
```

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
