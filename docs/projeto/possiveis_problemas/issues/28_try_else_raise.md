# Draft issue for ESBMC (not posted)

Reproducer: `28_raise_no_else_do_try_min.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] An exception raised in `try ... else:` is caught by the same try's `except`

### Reproducer
```python
try:
    y = 1
except ValueError:
    pass
else:
    raise ValueError("e")
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
The `else` clause is not covered by the handlers of its own `try` (Python reference, "The try statement").
CPython: uncaught `ValueError: e`. Expected `VERIFICATION FAILED` with `ValueError`.

### Actual
```
  PASSED       [global.assertion.1]  line 0  uncaught exception
  PASSED       [global.assertion.2]  line 0  uncaught exception: ValueError
VERIFICATION SUCCESSFUL
```
With `except KeyError` the result is `FAILED`, so the raise in `else` is matched against the try's own
handlers. Same result inside a function and with `except Exception`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
