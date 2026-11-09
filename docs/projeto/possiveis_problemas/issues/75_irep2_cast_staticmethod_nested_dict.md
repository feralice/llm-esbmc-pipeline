# Draft issue for ESBMC (not posted)

Reproducer: `75_staticmethod_dict_aninhado_irep2.py` (this folder). Measured on 08/11/2026, ESBMC master `822227ff96`, rechecked on `95f025adf4` (same result). Suggested labels: python, bug.
GitHub search on 08/11 (all 851 issues with the `python` label, filtered by title): no issue with this cause; #10121 is open but a different cause.
Classification: no complete workaround: without the class the abort goes away, but a related false negative shows up (`iface.get('flags').lower()` is not reported, CPython raises AttributeError).

---

**Title:** [python] A staticmethod returning a nested dict, iterated with `.items()` and read with `.get()`, aborts with irep2_cast_error

### Reproducer
```python
class C:
    @staticmethod
    def interfaces() -> dict[str, dict[str, str]]:
        return {"a": {}}

def f() -> None:
    for name, iface in C.interfaces().items():
        x = iface.get('flags')

f()
```

### Command
`esbmc main.py --unwind 5 --no-pointer-check --no-align-check`

### Expected
CPython runs without error. Expected `VERIFICATION SUCCESSFUL`.

### Actual
`ERROR: uncaught exception [16irep2_cast_error]: irep2: struct_union_member_names() called on incompatible type (type_id = pointer)`. A free function instead of the `@staticmethod` gives `SUCCESSFUL`. Not #10121 (open), which is a whole-string `"Optional[...]"` annotation.
