# Rascunho de issue para o ESBMC (não postado)

Achado em 16/10/2026 ao verificar av_real_07 com o oráculo de valor. Reprodutor:
`possiveis_problemas/45_nondet_str_contraexemplo.py`. Medido no ESBMC v8.6 (release oficial).
Rótulos sugeridos: `python`, `enhancement`.

---

**Title:** [python] Counterexample does not show the value of a nondet_str()

### Summary
When a property fails because of a string from `nondet_str()`, the counterexample does not print the
string. For `nondet_int()` it prints the value. Without the value, a tool cannot replay the
counterexample in CPython.

### Reproducer
```python
s: str = nondet_str()
assert s != "ab"
```

### Actual
`VERIFICATION FAILED`, and the trace has no state with the value of `s`:
```
[Counterexample]
State 1 file str_cx_min.py line 2 column 0 thread 0
Violated property:
  file str_cx_min.py line 2 column 0
  assertion return_value$_strcmp$1 != 0
```
With `--compact-trace`, the only state for `s` is a pointer: `s = &str_cx_min.py:1$nondet_str$1[0]`.

### Expected
A state with the string, as for integers. The same program with `x: int = nondet_int()` and
`assert x != 5` prints `x = 5`. For example: `s = "ab"`.

### Version
ESBMC 8.6.0 (release), `esbmc file.py`, default options.
