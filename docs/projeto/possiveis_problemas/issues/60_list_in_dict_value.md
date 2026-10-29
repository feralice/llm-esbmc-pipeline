# Draft issue for ESBMC (not posted)

Reproducer: `repro.py` (reduced from Tarefa 10 passo 4 case `7f4509a77e6f`, ansible `get_cpu_facts`).
Measured on 28/10/2026. Suggested labels: python, bug.
GitHub search on 28/10 ("List variable not found", open and closed): closest is #8916 (closed 21/10,
`cells[i].append(v)` on a nested list). Its reproducer now passes on 4a356e33eb; the dict-key form below
still fails, so this is a remaining case, not a duplicate.

---

**Title:** [python] `d[k].append(x)` on a list stored into an empty dict stops conversion

### Summary
When a dict starts as `{}` and a list is later stored under a key, calling a list method directly on
`d[k]` stops conversion with an empty list name in the message. CPython runs the program without error.

### Reproducer
```python
d = {}
d['p'] = []
d['p'].append("x")
assert len(d['p']) == 1
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check`

### Expected
CPython runs without error. Expected `VERIFICATION SUCCESSFUL`.

### Actual
```
ERROR: List variable not found: 
```

| program | ESBMC | CPython |
|---|---|---|
| above | refused | passes |
| `d['p'] = ["a"]` before the append | same error | passes |
| `d = {'p': []}` (list in the literal) | SUCCESSFUL | passes |
| `d: dict[str, list[str]] = {}` | SUCCESSFUL | passes |
| `lst = d['p']` then `lst.append("x")` | FAILED on the `assert` (wrong verdict: `len(d['p'])` is encoded as `strlen`) | passes |

The last row is a wrong verdict rather than a refusal. Same result with Bitwuzla and `--z3`.

### Version
ESBMC master 4a356e33eb (28 Oct 2026), Bitwuzla build, x86_64 Linux.
