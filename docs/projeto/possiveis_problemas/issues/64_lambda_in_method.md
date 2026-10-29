# Draft issue for ESBMC (not posted)

Reproducer: `lambda_em_metodo.py`. Measured on 28/10/2026. Suggested labels: python, bug.
GitHub search on 28/10 ("is not defined in function", "lambda", "lambda method", "nested function"):
no open issue. Closest, closed: #7328 (same message, for a lambda bound to a name inside a free function,
whose body subscripts the parameter; that shape now works) and #8226 (enclosing-scope names).

---

**Title:** [python] A lambda written inside a method does not bind its own parameter

### Summary
A lambda defined in a method body (here passed straight as an argument) is refused with
`Variable 'p' is not defined in function 'lam1'`, where `p` is the lambda's own parameter. The same code
in a free function is verified. A nested `def` in the method, the usual rewrite, is refused too.

### Reproducer
```python
def apply(f, x: int) -> int:
    return f(x)


class S:
    def run(self) -> int:
        return apply(lambda p: p + 1, 1)


assert S().run() == 2
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython runs without error (`apply` returns 2). Expected `VERIFICATION SUCCESSFUL`.

### Actual
```
ERROR: Variable 'p' is not defined in function 'lam1' at line 7.
```
Same with Z3 and without the two `--no-*-check` flags. Variations:
- `run` as a free function (`def run() -> int: return apply(lambda p: p + 1, 1)`): `VERIFICATION SUCCESSFUL`.
- `run` as a `@staticmethod`: same error.
- `apply` never calling `f`: same error, so the call through the parameter is not needed.
- `g = lambda p: p + 1; return apply(g, 1)` in the method: same error.
- A default argument (`lambda p, k=1: p + k`): same error.
- A nested `def inc(p: int) -> int` in the method, passed as `apply(inc, 1)`:
  `ERROR: Variable 'inc' is not defined in function 'run' at line 9.`
- `inc` moved to module level: `VERIFICATION SUCCESSFUL` (and `VERIFICATION FAILED` once the assert is
  changed to `== 3`).

### Version
ESBMC master 4a356e33eb (27 Oct 2026), Bitwuzla build, x86_64 Linux.
