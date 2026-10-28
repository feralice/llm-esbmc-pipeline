# Draft issue for ESBMC (not posted)

Reproducer: `47_len_sem_dunder_len.py` (variant below runs under CPython). Measured on 27/10/2026.
Suggested labels: python, bug. GitHub search on 27/10: no matching issue.

---

**Title:** [python] `len()` of an instance without `__len__` does not raise TypeError

### Summary
`len(obj)` on an instance whose class defines no `__len__` should raise `TypeError`. ESBMC instead models
it as a string length (the trace goes through `strlen`), so the TypeError is never reported.

### Reproducer
```python
class C:
    limit = 1

    def put(self) -> None:
        while len(self) >= self.limit:
            pass


C().put()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython: `TypeError: object of type 'C' has no len()`. Expected `VERIFICATION FAILED` with `TypeError`.

### Actual
```
  FAILED       [strlen.assertion.1]  line 93  unwinding assertion loop 1
  FAILED       [put.assertion.1]     line  5  unwinding assertion loop 2
VERIFICATION FAILED
```
Only unwinding assertions, no TypeError. Without `limit`, ESBMC reports `AttributeError` on `self.limit`,
while CPython stops at `len(self)` first with TypeError. Follows #9092, which made exceptions in `while`
conditions visible.

### Version
ESBMC master 4a356e33eb (27 Oct 2026), Bitwuzla build, x86_64 Linux.
