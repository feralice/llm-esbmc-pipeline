# Draft issue for ESBMC (not posted)

Reproducer: `24_numpy_shape_parametro.py`. Measured on 22/10/2026. Suggested labels: python, numpy, bug.

---

**Title:** [python] `np.array(data).shape[1]` on a 2-D list parameter is treated as 1-D

### Reproducer
```python
import numpy as np


def columns(data: list[list[float]]) -> int:
    adata = np.array(data)
    shape = adata.shape
    return 10 // (shape[1] - 3)


def main() -> None:
    columns([[0.0, 1.0, 2.0]])


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `shape == (1, 3)`, so `10 // 0` raises `ZeroDivisionError`. Expected `VERIFICATION FAILED` with
`ZeroDivisionError`.

### Actual
```
ERROR: Tuple index out of range (size: 1)
```
The shape of a `list[list[float]]` parameter is built with one dimension.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
