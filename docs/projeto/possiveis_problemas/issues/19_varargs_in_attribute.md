# Draft issue for ESBMC (not posted)

Reproducer: `19_args_em_atributo.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `*args` stored in an attribute in `__init__` fails type inference

### Summary
A constructor that stores its `*args` tuple in an attribute is refused. The same `*args` read in a plain
function is accepted.

### Reproducer
```python
class And:
    def __init__(self, *args):
        self._args = args

    def first(self) -> int:
        return self._args[0] // self._args[1]


def main() -> None:
    a = And(nondet_int(), 0)
    a.first()


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `ZeroDivisionError`. Expected `VERIFICATION FAILED` with `ZeroDivisionError`.

### Actual
```
ERROR: Type inference failed at line 3. Variable args not found
```
`def f(*args): t = args; return t[0]` with `assert f(1, 2) == 1` verifies, so the problem is specific to
the constructor or to the attribute store.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
