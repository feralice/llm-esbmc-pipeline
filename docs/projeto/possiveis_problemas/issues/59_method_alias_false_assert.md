# Draft issue for ESBMC (not posted)

Reproducer: `59_alias_de_metodo_sem_anotacao.py`. Measured on 27/10/2026. Suggested labels: python, bug.
GitHub search on 27/10 ("method alias"): no matching issue.

---

**Title:** [python] Calling a bound method through a local alias makes a true assert fail

### Summary
A bound method of an instance stored in a local variable and called through it returns a wrong value when the
method has no type annotations, so an assert that holds in CPython fails. This is a false positive.

### Reproducer
```python
class Operator:
    def lt(self, a, b):
        return a < b


operator = Operator()


def f(x: int, y: int) -> bool:
    op = operator.lt
    return op(x, y)


assert f(1, 2)
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython: the assert holds. Expected `VERIFICATION SUCCESSFUL`.

### Actual
```
  FAILED       [global.assertion.1]  line 14  assertion (signed int)py:main.py@__assert_temp == 1
VERIFICATION FAILED
```
With `def lt(self, a: int, b: int) -> bool`, ESBMC reports SUCCESSFUL.

### Version
ESBMC master 4a356e33eb (27 Oct 2026), Bitwuzla build, x86_64 Linux.
