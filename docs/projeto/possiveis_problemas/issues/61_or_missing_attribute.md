# Draft issue for ESBMC (not posted)

Reproducers: `repro.py` (abort) and `repro_fn.py` (false negative), this folder. Measured on 28/10/2026.
Suggested labels: python, bug.
GitHub search on 28/10 ("Can't generate zero for type empty", "generate zero for type empty",
"zero for type empty", "type empty python", "missing attribute or", "short-circuit attribute"): no matching
issue. Related: #9092 (closed 24/10 by #9113), which fixed a missing attribute as the whole `if`/`while`
condition; this is the same exception as an operand of `or`/`and`.

---

**Title:** [python] Missing attribute as an `or`/`and` operand aborts in an `if` and is lost in an assignment

### Summary
When an attribute that the class does not define is one operand of `or` or `and`, ESBMC does not raise
`AttributeError`. As the condition of an `if` or `while`, symex aborts with `Can't generate zero for type
empty`. As the right-hand side of an assignment inside a function, the exception is dropped and the result is
`VERIFICATION SUCCESSFUL`. The same attribute access alone reports `AttributeError` correctly.

### Reproducer 1 (abort)
```python
try:
    from esbmc import nondet_bool
except ImportError:
    def nondet_bool() -> bool:
        return True


class C:
    pass


c = C()
if nondet_bool() or c.limit:
    pass
```

### Reproducer 2 (false negative)
```python
class C:
    pass


def f(c):
    x = False or c.limit
    return x


f(C())
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
1. CPython raises `AttributeError: 'C' object has no attribute 'limit'` whenever `nondet_bool()` is
   `False` (the fallback above returns `True`, so the plain CPython run exits 0). Expected
   `VERIFICATION FAILED` with `uncaught exception: AttributeError`.
2. CPython raises `AttributeError: 'C' object has no attribute 'limit'`. Expected `VERIFICATION FAILED`.

### Actual
1. Exit code 134 (core dump):
```
Starting Bounded Model Checking
ERROR: Can't generate zero for type empty
```
2. `Generated 0 VCC(s), 0 remaining after simplification (0 assignments)` and `VERIFICATION SUCCESSFUL`.

| program (with `c = C()`) | ESBMC | CPython (left operand false) |
|---|---|---|
| `if nondet_bool() or c.limit: pass` | abort | `AttributeError` |
| `if nondet_bool() and c.limit: pass` | abort | no error (short-circuit) |
| `if c.limit or nondet_bool(): pass` | abort | `AttributeError` |
| `while nondet_bool() or c.limit: break` | abort | `AttributeError` |
| `b = nondet_bool()` then `if b or c.limit: pass` | abort | `AttributeError` |
| `if nondet_bool(): pass` / `elif c.limit: pass` | FAILED, `AttributeError` | `AttributeError` |
| module level: `x = nondet_bool() or c.limit` | FAILED, `AttributeError` | `AttributeError` |
| module level: `x = False or c.limit` | SUCCESSFUL | `AttributeError` |
| in a function: `x = False or c.limit` | SUCCESSFUL | `AttributeError` |
| in a function: `x = c.limit` | FAILED, `AttributeError` | `AttributeError` |

Same results with `--z3`, with `--unwind 10` and without `--multi-property`. Reduced from a harness of
tornado's `HTTP1Connection._can_keep_alive`, whose condition is
`"Content-Length" in headers or headers.get(...).lower() == "chunked" or start_line.method in (...)` with a
`start_line` that has no `method`.

### Version
ESBMC master 4a356e33eb (27 Oct 2026), Bitwuzla build, x86_64 Linux.
