# Draft issue for ESBMC (not posted)

Reproducer: `74_float_variavel_passada_por_self.py` (this folder). Measured on 08/11/2026, ESBMC master `822227ff96`, rechecked on `95f025adf4` (same result). Suggested labels: python, bug.
GitHub search on 08/11 (all 851 issues with the `python` label, filtered by title): same family as #9841; no open issue or PR for the variable form.
Classification: has a behaviour-preserving workaround (annotate the parameter).

---

**Title:** [python] A float variable passed to an unannotated method parameter through `self` crashes (SIGSEGV)

### Reproducer
```python
class M:
    def get_time(self, tnow):
        return int(tnow - 1.5)

    def idle(self):
        now: float = 0.0
        w = self.get_time(now)

M().idle()
```

### Command
`esbmc main.py --unwind 5 --no-pointer-check --no-align-check`

### Expected
CPython runs without error. Expected `VERIFICATION SUCCESSFUL`.

### Actual
`ESBMC caught SIGSEGV: this is an internal error, not a verification result.` With `tnow: float` annotated, with a free function, with the literal `0.0` instead of the variable, or without the `- 1.5`, the verdict is correct. Same family as #9841 (closed by #9860, which types the parameter from a literal passed by `self`); this variant passes a `float` variable.
