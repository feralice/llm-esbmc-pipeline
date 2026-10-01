# ESBMC-Python: what it accepts (measured on ESBMC 8.5, 2026-10-01)

The target function's body must stay exactly as in original.py. Everything around it is yours to
simplify until ESBMC converts the program.

## Build the harness like this
- Copy only the target function. You may add type annotations to its signature, never to its body.
- Replace its class with a minimal class: only the attributes the function reads, each annotated,
  set in a plain `__init__`. No inheritance, no original constructor, no `__new__`.
- Replace every library the function calls with a tiny stub in harness.py that returns a value of
  the right type (e.g. `class np:` with a `@staticmethod def ceil(x: float) -> float`). Do not
  import numpy, torch, requests, sys, json, itertools or functools.
- Annotate everything: parameters, returns, attributes, class-level variables.
- Inputs: `nondet_int()`, `nondet_float()`, `nondet_str()`, `nondet_bool()`. Lists: start empty and
  `if nondet_bool(): xs.append(...)` twice. Optional: start at None, then `if nondet_bool(): x = ...`.
  Sets of int/str work. Avoid `Union`, tuples containing None, and conditional expressions on
  Optional values (ESBMC models them wrongly).
- Call the function at the end. No `assert`, no guard around the suspect expression.
- Keep every stub inside harness.py; the CPython replay runs harness.py alone.

## Read the error, fix the surroundings
| ESBMC message | Fix |
|---|---|
| `Object/Function "X" not found` | define a stub for X |
| `Base class not found` | minimal class without the base |
| `Undefined function 'f' - replacing with assert(false)` | stub f, otherwise ESBMC reports a violation that is not there (e.g. `re.sub` has no model) |
| `Type inference failed` / `Cannot infer type for class attribute` | annotate that variable or attribute |
| `list indices must be integers, not str` | that input is a dict, not a list |
| `Cannot unpack ...` | that value must be a tuple with exactly that many items |
| `X is not yet supported` (e.g. `threading.RLock`) | minimal class with no-op methods |
| `Unsupported NumPy function` | stub numpy |
| `error: ... [no-untyped-def]` | mypy warning only; ignore it |
| only `unwinding assertion` violations | rerun with a larger `--unwind` (10, then 20) |

## Known ESBMC-Python traps
- A method of your own class named `get` is resolved as `dict.get`; call sites still must stay as in
  the original body, so keep the class minimal around it.
- `re.match` with a pattern of at most one character always returns a match in ESBMC's model.
- `sys.exit` is replaced by `assert(false)`: stub `sys` with an `exit` that ends the path.

## When it cannot work
If the error comes from the function body itself (`x.__dict__`, `type(x).__name__`, `*args`/`**kwargs`,
`"%d" % value`, `sorted(..., key=...)` over a non-constant list, `async`), no harness fixes it without
rewriting the function. Stop and reply DONE: that is a limit of ESBMC-Python, not of the harness.
