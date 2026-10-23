# Draft issue for ESBMC (not posted)

Reproducer: `20_kwargs.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `**kwargs` in `__init__` still refused after #9002

### Summary
#8497 was closed by #9002, which lowers `**kwargs` by specializing each call. A constructor that reads its
`**kwargs` is still refused on master, with or without keyword arguments at the call site.

### Reproducer
```python
class Box:
    def __init__(self, **kw):
        self._error = kw.get('error')

    def div(self, n: int) -> int:
        return n // 0 if self._error is None else n


def main() -> None:
    b = Box()
    b.div(nondet_int())


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `ZeroDivisionError`. Expected `VERIFICATION FAILED` with `ZeroDivisionError`.

### Actual
```
ERROR: Object "kw" not found.
```
Same message with `Box(error=1)`. For comparison, on the same commit:

| program | ESBMC | CPython |
|---|---|---|
| `def f(**kw): return kw.get('a', 1)`, `assert f(a=2) == 2` | SUCCESSFUL | passes |
| `def f(**kw): return kw.get('error')`, `assert f() is None` | FAILED: `None returned from a function whose return type cannot hold None` | passes |

The last row is a false positive in the plain function case (same with `f(x=1)`).

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
