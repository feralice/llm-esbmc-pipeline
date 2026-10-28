# Draft issue for ESBMC (not posted)

Reproducer: `56_atributo_criado_em_outra_instancia.py`. Measured on 27/10/2026. Suggested labels: python, bug.
GitHub search on 27/10: no matching issue. Related but different: #8632 (attribute created on one path of the
same object, fixed), #8844 (base `__init__` not called, now refused), #9308 (conditional `super().__init__`).

---

**Title:** [python] An attribute set on one instance is treated as present on every instance of the class

### Summary
When an attribute is created outside `__init__` on one object, reading it on another instance of the same class
does not raise `AttributeError`. This is a false negative: CPython raises.

### Reproducer
```python
class R:
    pass


a = R()
b = R()
a.prev = None
b.prev
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython: `AttributeError: 'R' object has no attribute 'prev'` on the last line. Expected `VERIFICATION FAILED`.

### Actual
```
  PASSED       [global.assertion.4]  line 8  uncaught exception: AttributeError
VERIFICATION SUCCESSFUL
```
Without the line `a.prev = None`, ESBMC reports the AttributeError as expected. Found on real code
(ansible `pamd.py`: `PamdRule.__init__` does not call the base `__init__` that sets `prev`, and
`PamdService.append` sets `prev` on the other nodes).

### Version
ESBMC master 4a356e33eb (27 Oct 2026), Bitwuzla build, x86_64 Linux.
