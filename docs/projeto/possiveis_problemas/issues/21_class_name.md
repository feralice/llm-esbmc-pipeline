# Draft issue for ESBMC (not posted)

Reproducer: `21_class_name.py`. Measured on 22/10/2026. Suggested labels: python, enhancement.

---

**Title:** [python] `self.__class__.__name__` is refused (Cannot resolve nested attribute)

### Reproducer
```python
class Schema:
    def __init__(self, n: int):
        self.n = n

    def describe(self) -> str:
        return self.__class__.__name__ + str(10 // self.n)


def main() -> None:
    Schema(0).describe()


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `ZeroDivisionError`. Expected `VERIFICATION FAILED` with `ZeroDivisionError`.

### Actual
```
ERROR: Cannot resolve nested attribute: __name__
```

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
