# Draft issue: Python `Optional[tuple[float, float]]` causes solver sort error

**Status:** substituído em 03/11 por `docs/projeto/possiveis_problemas/issues/69_optional_tuple_sort_error.md` (mesmo bug, reproducer menor no master `0945ac9`).

## Reproducer

```python
from typing import Optional


class Panel:
    def __init__(self) -> None:
        value: Optional[tuple[float, float]] = None
        if nondet_bool():
            value = (nondet_float(), nondet_float())
        self.click_pos: Optional[tuple[float, float]] = value

    def read(self) -> None:
        if self.click_pos is None:
            return
        x = self.click_pos[0]
        assert x == x


Panel().read()
```

Command:

```sh
esbmc --no-pointer-check --no-align-check --unwind 5 --multi-property repro.py
```

## Observed result

ESBMC 8.6.0, local source commit `d520a903aef7f9585355e07e1fb92cb16982c588`,
on Linux x86_64, exits with status 70. The default Bitwuzla backend reports:

```text
ERROR: the per-claim solve loop did not finish (exception: invalid call to
'bitwuzla::Term bitwuzla::TermManager::mk_term(...)', term with unexpected sort at index 0)
ERROR: uncaught exception [N8bitwuzla9ExceptionE]: invalid call to
'bitwuzla::Term bitwuzla::TermManager::mk_term(...)', term with unexpected sort at index 0
```

The same reproducer with `--z3` reports incompatible sorts between an
`Optional` tuple struct and a plain tuple struct. Removing `--multi-property`
does not avoid the Bitwuzla error. The Python frontend also prints
`WARNING: typing.Optional module-file-not-found` before conversion.

## Expected result

The verifier should finish with a verification result for the assertion, or
reject this Python construct with a clear unsupported-feature message.
A solver type exception leaves the property undecided.

## Context

The error was first seen in a generated harness for a MAVProxy function.
The small program above reproduces it without the MAVProxy source or the
research pipeline. The `assert x == x` property may itself fail for NaN;
the issue is the internal sort exception before a result is produced.
