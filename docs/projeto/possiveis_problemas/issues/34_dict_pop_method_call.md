# Draft issue for ESBMC (not posted)

Reproducer: `34_pop_encadeado.py`. Measured on 22/10/2026. Suggested labels: python, enhancement.

---

**Title:** [python] Method call on the result of `dict.pop` is refused (class is not known)

### Summary
`d.pop(k).m()` on a `dict[str, Job]` is refused, although the value type is declared. Assigning the
result first (`j = jobs.pop("b")`) verifies and reports the `KeyError`.

### Reproducer
```python
class Job:
    def __init__(self) -> None:
        self.n: int = 0

    def stop(self) -> int:
        return self.n


def main() -> None:
    jobs: dict[str, Job] = {"a": Job()}
    jobs.pop("b").stop()


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
CPython: `KeyError: 'b'`. Expected `VERIFICATION FAILED` with `KeyError`.

### Actual
```
ERROR: unsupported: calling method 'stop' on a value whose class is not known
```
Before this message was added, the same program gave `VERIFICATION SUCCESSFUL`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
