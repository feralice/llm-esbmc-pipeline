# Draft issue for ESBMC (not posted)

Reproducer: `14_async.py, 14_async_run.py`. Measured on 22/10/2026. Suggested labels: python, enhancement.

---

**Title:** [python] `async def` is refused (AsyncFunctionDef statements are not supported)

### Summary
Any module that defines a coroutine function is refused before verification, even when the coroutine is
only created and never awaited, or is run with `asyncio.run`.

### Reproducer
Plain call (the body never runs in CPython):
```python
async def ratio(a: int, b: int) -> int:
    return a // b


def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    ratio(a, b)


main()
```

Awaited with `asyncio.run`:
```python
import asyncio


async def ratio(a: int, b: int) -> int:
    return a // b


def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    asyncio.run(ratio(a, b))


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
- Plain call: CPython only creates the coroutine (`RuntimeWarning: coroutine 'ratio' was never awaited`);
  the division is never executed. Expected `VERIFICATION SUCCESSFUL`.
- `asyncio.run`: CPython raises `ZeroDivisionError` when `b == 0`. Expected `VERIFICATION FAILED` with
  `ZeroDivisionError`.

### Actual
Both programs:
```
ERROR: AsyncFunctionDef statements are not supported
```

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
