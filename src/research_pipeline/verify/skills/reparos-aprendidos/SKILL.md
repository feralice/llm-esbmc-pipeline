---
name: reparos-aprendidos
description: Repairs learned from earlier harness attempts that ESBMC-Python rejected. Use together with regras-harness.
---

# Learned repairs

### Annotate attributes that start as None with their class
- Error: `ERROR: Cannot resolve nested attribute: <name>`
- What to do: where `__init__` sets `self.x = None` and code later reads `obj.x.y`, annotate it with the
  class it will hold, unquoted: `self.x: Node = None`. The value stays None, so behaviour is unchanged.
- Source case: 6e33562fdd8f (nm_real_12), rounds 4 and 7.
- Approval date: 2026-10-27.

### Automatic repair 9bcdb542c415: ERROR: Cannot resolve nested attribute: scale
- Origin: automatica
- Error: `ERROR: Cannot resolve nested attribute: scale`
- What to do: the change below made ESBMC reach a verdict (UNVALIDATED) without changing the target function's behaviour.
```diff
+def _dump_signal(signal: Signal = None) -> str:
+    return nondet_str()
```
- Source case: 792b86d01c11, round 0
- Run: artifacts/pgene601/rodada-final-2026-11-09
- Date: 2026-11-09.
- Key: 9bcdb542c415

### Automatic repair daf1cff17e66: undefined name(s): time
- Origin: automatica
- Error: `undefined name(s): time`
- What to do: the change below made ESBMC reach a verdict (CONFIRMED) without changing the target function's behaviour.
```diff
-import time, os, sys
+import os, sys
+class _TimeModule:
+    def __init__(self) -> None:
+        self.marker: int = nondet_int()
+
+    def time(self) -> float:
+        return nondet_float()
+
+
+time: _TimeModule = _TimeModule()
```
- Source case: f1c85fab4a89, round 0
- Run: artifacts/pgene601/rodada-final-2026-11-09
- Date: 2026-11-09.
- Key: daf1cff17e66

### Automatic repair ea1b0394cf7c: ERROR: Variable 'kwargs' is not defined in function 'ReadDeviceInformationRespon
- Origin: automatica
- Error: `ERROR: Variable 'kwargs' is not defined in function 'ReadDeviceInformationResponse' at line 69.`
- What to do: the change below made ESBMC reach a verdict (CONFIRMED) without changing the target function's behaviour.
```diff
-def __init__(self, read_code=None, object_id=0x00, **kwargs):
+def __init__(self, read_code=None, object_id=0x00):
-ModbusRequest.__init__(self, **kwargs)
+ModbusRequest.__init__(self)
-def __init__(self, read_code=None, information=None, **kwargs):
+def __init__(self, read_code=None, information=None):
-ModbusResponse.__init__(self, **kwargs)
+ModbusResponse.__init__(self)
```
- Source case: 105b4c417676, round 0
- Run: artifacts/pgene601/rodada-final-2026-11-09
- Date: 2026-11-09.
- Key: ea1b0394cf7c

### Automatic repair 6f0907585613: ERROR: Element size cannot be zero
- Origin: automatica
- Error: `ERROR: Element size cannot be zero`
- What to do: the change below made ESBMC reach a verdict (UNVALIDATED) without changing the target function's behaviour.
```diff
+class _SerialModule:
+    def __init__(self) -> None:
+        self.marker: int = nondet_int()
+
+    def iterbytes(self, data: str = None) -> str:
+        return nondet_str()
+
+
+serial: _SerialModule = _SerialModule()
```
- Source case: 36120577a66a, round 1
- Run: artifacts/pgene601/rodada-final-2026-11-09
- Date: 2026-11-09.
- Key: 6f0907585613

### Automatic repair c030c5373bbc: ERROR: Object "kwargs" not found.
- Origin: automatica
- Error: `ERROR: Object "kwargs" not found.`
- What to do: the change below made ESBMC reach a verdict (UNVALIDATED) without changing the target function's behaviour.
```diff
+class _KwargsStub:
+    def __init__(self) -> None:
+        self.marker: int = nondet_int()
+
+    def get(self, key: str = None, default: str = None) -> str:
+        return nondet_str()
+
+
+kwargs: _KwargsStub = _KwargsStub()
```
- Source case: a680e44eda1a, round 0
- Run: artifacts/pgene601/rodada-final-2026-11-09
- Date: 2026-11-09.
- Key: c030c5373bbc

### Automatic repair 4a510d776f38: ERROR: 'os' at line 22 is bound both by an import and by another statement, and 
- Origin: automatica
- Error: `ERROR: 'os' at line 22 is bound both by an import and by another statement, and the Python frontend cannot tell which binding it reads`
- What to do: the change below made ESBMC reach a verdict (CONFIRMED) without changing the target function's behaviour.
```diff
-
-import os
+
```
- Source case: b0b7c851d9c7, round 1
- Run: artifacts/pgene601/rodada-final-2026-11-09
- Date: 2026-11-09.
- Key: 4a510d776f38

### Automatic repair 06f04dc72704: ERROR: Cannot unpack pointer - only tuples and arrays can be unpacked
- Origin: automatica
- Error: `ERROR: Cannot unpack pointer - only tuples and arrays can be unpacked`
- What to do: the change below made ESBMC reach a verdict (OTHER_FAILURE) without changing the target function's behaviour.
```diff
-import importlib
+class _HandlerModule:
+    def __init__(self) -> None:
+        self.marker: int = nondet_int()
+
+    def serial_class_for_url(self, url: str = None) -> tuple[str, str]:
+        return (nondet_str(), nondet_str())
+
+
+class _ImportlibModule:
+    def __init__(self) -> None:
+        self.marker: int = nondet_int()
+
+    def import_module(self, name: str = None, package: str = None) -> _HandlerModule:
+        return _HandlerModule()
+
+
+importlib: _ImportlibModule = _ImportlibModule()
```
- Source case: ba4058a71ffa, round 2
- Run: artifacts/scan_pyserial_2026-11-10
- Date: 2026-11-10.
- Key: 06f04dc72704

### Automatic repair 242503d53afc: ERROR: NameError: name 'memoryview' is not defined
- Origin: automatica
- Error: `ERROR: NameError: name 'memoryview' is not defined`
- What to do: the change below made ESBMC reach a verdict (UNVALIDATED) without changing the target function's behaviour.
```diff
+class memoryview:
+    def __init__(self) -> None:
+        self.marker: int = nondet_int()
+
+    def tobytes(self) -> str:
+        return nondet_str()
```
- Source case: 9e86868d788e, round 0
- Run: artifacts/scan_pyserial_2026-11-10
- Date: 2026-11-10.
- Key: 242503d53afc

### Automatic repair aabd19a75840: ERROR: Cannot infer type for class attribute 'echo' in class 'NoTerminal'. Pleas
- Origin: automatica
- Error: `ERROR: Cannot infer type for class attribute 'echo' in class 'NoTerminal'. Please add explicit type annotation.`
- What to do: the change below made ESBMC reach a verdict (UNVALIDATED) without changing the target function's behaviour.
```diff
-    echo = rx
-
-
-class NoControls(NoTerminal):
+    def echo(self, text: str = None) -> str:
+        return self.rx(text)
+
+
+class NoControls(NoTerminal):
-        return ''.join(r)
-
-    echo = rx
+        return ''.join(r)
+
+    def echo(self, text: str = None) -> str:
+        return self.rx(text)
```
- Source case: d6833d552492, round 3
- Run: artifacts/scan_pyserial_2026-11-10
- Date: 2026-11-10.
- Key: aabd19a75840

## Format of an approved repair

Since 05/11 the hybrid and scan runs add a repair here by themselves (Origin: automatica) as soon as it made
ESBMC reach a verdict on a harness it refused, unless the run passes `--no-auto-lessons`; the same rule is never
added twice (Key). Older runs are reviewed with `scripts/v2_repair_candidates.py` (candidatos.md) or the
`/self-healing` command, and a repair the researcher approves enters through `scripts/add_repair.py`, which checks
this format; never edit this file by hand. Its version is the hash of this file, which each case records. Each
approved rule:


### Give container elements a class when the code reads attributes on them
- Error: `ERROR: Cannot resolve attribute '<name>' on Subscript result` (also `Cannot resolve nested attribute`
  when the owner is an element of a list or dict, or a function parameter whose class is `pass`).
- What to do: ESBMC types `x[i].name` only when the element type is a class that declares `name`. Do three things in
  ONE patch: (1) define `class C:` with `__init__` setting each read attribute to `nondet_<type>()` (a float when it is
  compared with a float, an int when with an int); (2) change every annotation and every creation site of the
  container from `list[int]`, `list[object]` or `_Opaque` to `list[C]` with `C()` elements; (3) if a callee reads the
  attributes and is not the target, replace the callee by a stub returning `nondet_<return type>()`.
  Do not add the class alone: an annotation that still says `list[int]` keeps the error.
- Source case: ce5b6f0a3656 (opcua_1131) and 6bb76036eb38 (pymavlink_1217), 08/11, three rounds each: the class was
  added in one round and the annotation changed in another, so ESBMC never saw both.
- Origin: manual (written 2026-11-09, waits for Fernanda's review).

### <short title>
- Error: the first `ERROR:` line ESBMC printed for the refused harness.
- What to do: the rewrite that made ESBMC reach a verdict without changing the function's behaviour.
- Source case: the hypothesis id and round the pair came from.
- Approval date: YYYY-MM-DD.

An automatic rule has Origin, Error, What to do (with the change as a diff), Source case, Run (the output
folder), Date and Key.
