# Draft issue for ESBMC (not posted)

Reproducer: `47_len_sem_dunder_len_min.py, 46_super_com_len_aborta_min.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] An exception raised in an `if`/`while` condition is lost, or aborts the encoder

### Summary
Exceptions that the frontend raises for a missing `__len__` or a missing attribute are dropped when the
expression is the condition of an `if` or `while`. The same expression outside a condition reports the
exception. When a `while` condition raises and another property follows the loop, ESBMC aborts on a
`cpp_throw` it cannot encode.

### Reproducer 1 (false negative)
```python
class C:
    pass


c = C()
if len(c) > 0:
    pass
```

### Reproducer 2 (abort)
```python
class C:
    pass


c = C()
while c.limit:
    pass
x = 1 // 0
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
1. CPython: `TypeError: object of type 'C' has no len()`. Expected `VERIFICATION FAILED` with `TypeError`.
2. CPython: `AttributeError: 'C' object has no attribute 'limit'`. Expected `VERIFICATION FAILED` with
   `AttributeError`.

### Actual
1. `Generated 0 VCC(s)` and `VERIFICATION SUCCESSFUL`.
2. Exit code 134:
```
Solving claim 'uncaught exception: ZeroDivisionError at file main.py line 8 column 8' with solver Z3 v4.13.3
ERROR: Couldn't convert expression in unrecognised format
cpp_throw
```

| program | ESBMC | CPython |
|---|---|---|
| `n = len(c)` | FAILED, `TypeError` | `TypeError` |
| `x = 1 if len(c) > 0 else 2` | FAILED, `TypeError` | `TypeError` |
| `if len(c) > 0: pass` | SUCCESSFUL | `TypeError` |
| `while len(c) > 0: pass` | SUCCESSFUL | `TypeError` |
| `x = c.limit` | FAILED, `AttributeError` | `AttributeError` |
| `if c.limit: pass` | SUCCESSFUL | `AttributeError` |
| `while c.limit: pass` | SUCCESSFUL | `AttributeError` |
| `while c.limit: pass` then `x = 1 // 0` | abort (`cpp_throw`) | `AttributeError` |
| `if 10 // n > 0: pass`, `n = 0` | FAILED, `ZeroDivisionError` | `ZeroDivisionError` |

Reduced from a harness where `while len(self) >= self.limit:` was followed by `super(...).put(key)`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
