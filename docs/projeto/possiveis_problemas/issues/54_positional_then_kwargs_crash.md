# Draft issue for ESBMC (not posted)

Reproducer: `54_chamada_posicional_mais_kwargs.py`. Measured on 27/10/2026. Suggested labels: python, bug.
GitHub search on 27/10 ("type_error.302"): #9274 and #6281 hit the same nlohmann error from other constructs
(both closed); none with `**` at a call site.

---

**Title:** [python] A call with an explicit argument followed by `**dict` aborts with nlohmann type_error.302

### Summary
A call to a user function that mixes an explicit (positional or keyword) argument with `**expr` aborts the
converter. `g(**d)` alone does not abort.

### Reproducer
```python
def g(a):
    return a


d = {}
g(1, **d)
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython runs without error. Expected `VERIFICATION SUCCESSFUL`.

### Actual
```
ERROR: [json.exception.type_error.302] type must be string, but is null
```
during "Converting" (exit code 6). Same with `g(1, **{})` and `g(a=1, **d)`. In the AST JSON the keyword
for `**d` has `"arg": null`, which the converter seems to read as a string.

### Version
ESBMC master 4a356e33eb (27 Oct 2026), Bitwuzla build, x86_64 Linux.
