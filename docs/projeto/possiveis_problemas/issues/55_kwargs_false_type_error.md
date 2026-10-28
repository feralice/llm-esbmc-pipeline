# Draft issue for ESBMC (not posted)

Reproducer: `55_kwargs_falso_type_error.py`. Measured on 27/10/2026. Suggested labels: python, bug.
GitHub search on 27/10 ("**kwargs TypeError"): no matching issue.

---

**Title:** [python] Unpacking a dict with `**` into a call reports a spurious TypeError

### Summary
Passing a dict that holds every required argument with `**d` makes ESBMC report an uncaught
`TypeError`, although CPython binds the arguments and runs without error. This is a false positive.

### Reproducer
```python
def g(a):
    return a


d = {"a": 1}
g(**d)
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython runs without error. Expected `VERIFICATION SUCCESSFUL`.

### Actual
```
  FAILED       [global.assertion.2]  line 0  uncaught exception: TypeError
VERIFICATION FAILED
```
Same result with `def f(**kw): return g(**kw)` called as `f(a=1)`. With `d = {}` the FAILED is correct
(CPython also raises TypeError, `a` is missing).

### Version
ESBMC master 4a356e33eb (27 Oct 2026), Bitwuzla build, x86_64 Linux.
