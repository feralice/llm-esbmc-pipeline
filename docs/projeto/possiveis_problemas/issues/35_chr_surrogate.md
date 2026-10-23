# Draft issue for ESBMC (not posted)

Reproducer: `35_chr_surrogate.py`. Measured on 22/10/2026. Suggested labels: python, bug.

---

**Title:** [python] `chr()` of a surrogate code point is reported as an error (false positive)

### Reproducer
```python
def main() -> None:
    n = nondet_int()
    if 0xD800 <= n <= 0xDFFF:
        c = chr(n)


main()
```

### Command
`esbmc main.py --unwind 5 --multi-property --no-pointer-check --no-align-check` (Z3 build; the Bitwuzla build with `--bitwuzla` gives the same result; same result with `--unwind 10` and without `--multi-property`)

### Expected
`chr()` accepts every code point in `range(0x110000)`, surrogates included (`chr(0xD800)` returns
`'\ud800'`). The program runs without error in CPython. Expected `VERIFICATION SUCCESSFUL`.

### Actual
```
  n = 55296
Violated property:
  chr() arg is a surrogate code point
  FAILED       [__python_chr.assertion.2]  line 1426  chr() arg is a surrogate code point
VERIFICATION FAILED
```
With the literal `chr(0xD800)` the program is refused: `Code point 0xD800 is a surrogate pair, invalid in UTF-8`.

### Version
ESBMC master 7da3564989 (22 Oct 2026), x86_64 Linux.
