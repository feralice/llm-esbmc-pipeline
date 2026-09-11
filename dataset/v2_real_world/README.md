# V2 Real-World Dataset

Implements the direction proposed in [`docs/v2/harness_synthesis.md`](../../docs/v2/harness_synthesis.md):
real bugs from [BugsInPy](https://github.com/soarsmu/BugsInPy), abstracted by hand into
self-contained, ESBMC-verifiable harnesses. Complements the synthetic, controlled V1 dataset at
`dataset/labeled/` — V1 answers "can the pipeline confirm a known bug shape", V2 answers "does that
transfer to bugs nobody wrote for a benchmark".

## Layout

Reorganized from the original per-category-folder shape (kept in git history if needed) into a
single flat structure, since several bugs genuinely fit more than one category and a folder-per-
category layout forces a single primary label per file:

- `bugs/` — every confirmed item's `.py` harness in one flat folder (106 files, no subfolders)
- `ground_truths.json` — one file for all items, with a `provenance` block per item linking back to
  the real project/commit, `abstraction_notes`, and a `categories` field (a **list**, not a single
  string) — most items have one category, a small number genuinely have two (see Method below).
  The primary `function`/`expression` fields describe the neutral `detection/` source. The
  ESBMC-oracle harness target is stored separately as `harness_file`, `harness_function`,
  `harness_expression`, and `harness_line`.

The old `ground_truths/<category>.json` + `bugs/<category>/` layout is gone; anything that read
`expected_category` as a single string should read `categories[0]` for the primary label or check
`category in categories` for full membership.

## Method

1. Read the real fix patch (`bug_patch.txt`) for a BugsInPy-tagged bug, not just its category label
   — several category tags in the automated candidate scan (`analyze_bugs_v2.py`) turned out to be
   wrong on close reading (see Findings below).
2. Isolate the scalar/logic core that carries the bug — no numpy/pandas/external imports.
3. Where the real code needs an external object (a pandas index type, a dict lookup, an
   attribute's liveness), stub the *minimum* needed shape (an int tag, a bool flag) rather than
   importing the real dependency, per the stub-shadowing approach `docs/v2/harness_synthesis.md`
   §5.2 and §6 call for.
4. Preserve the real caller's actual precondition (what the original code already guarantees)
   instead of inventing a stricter one — this is what makes the counterexample mean something.
5. Type-hint everything, `nondet_*`/`__ESBMC_assume` bare (no import), verify with `--z3`.
6. Confirmed every item with `esbmc file.py --z3 --unwind 6 --timeout 20s`: all produce
   `VERIFICATION FAILED` with `Generated N VCC(s)`, `N > 0` — not the 0-VCC false "SUCCESSFUL" this
   session hit on a first pass (see `~/.claude/skills/esbmc-python-guide/SKILL.md` §4).
7. **Multi-category tagging (added after the flat-layout reorganization)**: a second category is
   added to an item's `categories` list only when its *own* `abstraction_notes` describe a second,
   genuinely distinct fault mechanism actually present in that bug — not because the categories are
   thematically close. Concretely: `none_misuse` and `invalid_precondition` are *structurally*
   related in almost every item in this dataset (a missing None-check is, by definition, a missing
   precondition), so that pairing is deliberately **not** applied wholesale — it's reserved for the
   handful of items whose notes explicitly describe a None value silently reaching logic that
   assumes a real value ("silently accepted `columns=None`", "`dict.get()` with no default returned
   `None`... crashing downstream") rather than the generic "missing a guard" shape most
   `invalid_precondition` items share. Same bar applied to `out_of_bounds`↔`invalid_precondition`
   (only when the real defect is a silent wrong-value bug modeled the buggy/correct way, not a raised
   `IndexError`) and `none_misuse`↔`variable_misuse` (only when state genuinely leaks/is stale across
   iterations, the same shape as `vm_real_01`/`vm_real_02`, not just "a None involved somewhere").
   10 of 106 items got a second tag; the other 96 stayed single-category on purpose.

## Findings worth keeping for the write-up

- **`integer_overflow` has one scalar-abstraction case**: `matplotlib/16` and `matplotlib/17` refer
  to the same underlying patch in `transforms.py::nonsingular`, so they count as one bug rather than
  two independent observations. The real trigger is fixed-width NumPy arithmetic
  (`abs(np.int8(-128)) == -128`). Direct `np.int8` remains unsupported by ESBMC-Python; `io_real_01`
  therefore models signed 8-bit two's-complement `abs` explicitly and preserves the real int8 input
  domain. Its counterexample is evidence on that scalar abstraction, not evidence that ordinary
  Python `int` overflows (Python integers have arbitrary precision).
- **A new small category, `variable_misuse`**: `tqdm/8` (stale `l_bar`/`r_bar` formatted instead of
  the freshly split `l_bar_user`/`r_bar_user`, silently ignoring a custom `bar_format`) doesn't fit
  any of the six existing categories — it's not a missing precondition, type confusion, or None
  dereference, just the wrong local variable read. One item so far (`vm_real_01`); revisit whether
  it's worth folding into `invalid_precondition` or keeping standalone once more examples turn up.
- **`str.replace()` is too expensive to verify, even on short literal strings, not just nondet
  ones**: `thefuck/27` (`get_new_command`, buggy `'open http://' + script[5:]` vs fixed
  `script.replace('open ', 'open http://')`) and `thefuck/31`-shaped `.replace()` bugs cost seconds
  with `nondet_str()` and still time out on a single 14-character literal string at `--unwind 40`
  (`--timeout 20s`+) — the underlying `strncmp`/`strstr` loop in the C string model appears to scan
  against the full `max_len = 1<<16` symbolic buffer regardless of the concrete string's actual
  length. Dropped both without a harness; worth a real ESBMC-side look (`string_handler.cpp`) before
  attempting any other `.replace()`-based candidate.
- **`dict.update()` looks like it silently no-ops in ESBMC-Python — flagged for a real check, not
  confirmed as a dataset bug**: a minimal probe (`config = {0: 1}; config.update({0: 2});
  assert config[0] == 2`) fails the assertion, i.e. the key is NOT overwritten as real Python
  `dict.update()` guarantees. This blocked a faithful `spacy/2` harness (`config.update(overrides)`
  missing in the real buggy code) since the buggy-vs-correct pair collapsed to the same wrong value
  either way. Not investigated further here — this is a candidate for `esbmc-verifier` Mode A
  (ESBMC's own bug), not a `v2_real_world` dataset item.
- **5 more confirmed via `esbmc --z3`, all `VERIFICATION FAILED` with VCC>0**: `oob_real_06`
  (thefuck/21, `split()[1]` IndexError, verbatim), `oob_real_07` (thefuck/22, `_cached[0]` IndexError,
  verbatim), `oob_real_08` (black/17, `src_txt[-1]` IndexError on empty string, verbatim, second hunk
  of the same patch as `oob_real_05`), `av_real_12` (thefuck/7, buggy/correct substring-match pair,
  concrete literal input), `av_real_13` (thefuck/5, same pattern, git-push stderr substring match).
  Deferred without a harness (time budget, not rejected): `youtube-dl/18`, `youtube-dl/6`, `luigi/1`.
- **Two more "other" candidates confirmed as real ESBMC-Python limitations, not abstraction
  failures**: `PySnooper/3` (`open(output_path, ...)` referencing an undefined name — real
  `NameError`) and `luigi/13` (`self.fs.mkdir(d)` where `self.fs` doesn't exist on the class — real
  `AttributeError`) both fail at *conversion time* with a static `ERROR:`, not a VCC-based
  counterexample (`luigi/13`'s probe: `Could not resolve type of receiver in member call
  '.fs.mkdir()'`). ESBMC-Python's type checker/converter rejects the malformed attribute chain
  before symbolic execution ever starts, so neither fits the "VERIFICATION FAILED" dataset schema.
- **`/` vs `//` in ESBMC-Python**: true division always lowers to `ieee_div` (IEEE float), which is
  *not* covered by the default division-by-zero check — only integer `//` is. `dz_real_01` needs a
  manual `assert denom != 0` to make the real ZeroDivisionError semantics checkable at all.
- **Category-scarcity in BugsInPy for `division_by_zero`**: across all 501 tracked bugs, only 2
  patches even superficially matched a "division by a variable" pattern, and on full read only 1
  (`matplotlib/30`) was a real zero-division bug — the other (`matplotlib/15`) was a log-base
  parameterization change misclassified by the automated heuristic.
- **`assertion_violation` in BugsInPy is dominated by pandas internals**: 13 of 20 automated
  candidates depend on pandas-internal types (`PeriodIndex`, `ABCIndex`, `ExtensionIndex`) not
  reachable without stubbing; of the rest, most had an `assert` line present only as unrelated
  diff context — the real fix was elsewhere (regex, encoding, dict-merge aliasing). Only
  `youtube-dl/17` was clean out of the box; `tornado/1` and `pandas/3` needed stubbing;
  `pandas/52`, `pandas/94`, `pandas/123`, `black/14`, `black/16`, `black/23`, `fastapi/13`,
  `tornado/2`, `PySnooper/3`, `youtube-dl/3` were rejected after full-patch reading.
- **`thefuck` is the best-yielding project for `out_of_bounds`**: small, pure, dependency-free
  rule functions built around string parsing — 3 of 3 candidates checked here held up
  (`re.findall()[0]`, `.split()[i]`, double `.pop(idx)`); `thefuck/15` looked promising by grep but
  didn't hold up on full read (the diff loosens a match guard, it doesn't fix a crash).
- **A 4th category, `none_misuse`, emerged from widening the search past the original three
  projects**: real code that assumes a value is never `None` and gets away with it until a
  legitimate code path (an explicitly-unset value, an iterable with no `__len__`) leaves it `None`.
  `httpie/3` (`value.decode('utf8')` on an explicitly-unset header, real `AttributeError`) and
  `tqdm/4` (`total *= unit_scale` when `total` is still `None`, real `TypeError`) both held up on
  full read and are dependency-free. Neither operation (`bytes.decode`, `None`-typed arithmetic) is
  modeled by ESBMC-Python, so both harnesses make the crash explicit via an `assert` on the
  precondition it actually depends on (`not value_is_none`), the same technique `dz_real_01`
  already uses for `ieee_div`.
- **Widening past `thefuck`/`youtube-dl`/`pandas`/`matplotlib`/`black`/`tornado` mostly confirmed the
  existing pattern rather than opening new ground**: `sanic` (2, 3, 4), `ansible/5`, `keras` (1, 20),
  `cookiecutter/1`, `fastapi/1`, and a batch of small pandas patches (`pandas/54`, `77`, `145`) all
  looked promising by grep (`AttributeError`/`assert`/`ValueError`/`OverflowError` hits) but turned
  out on full read to be feature additions, test-only asserts, or numpy/pandas-internal dtype
  plumbing, not a crash abstractable without heavy stubbing. `scrapy/18`'s `except IndexError` was
  already present pre-patch (the real fix was an encoding change), a category-mismatch trap the same
  shape as the `thefuck/15` one already in this file. `thefuck/9` reappeared under the broadened scan
  and is already `oob_real_03` — no new find, just confirms the original candidate was solid.
- **`OverflowError` is not a productive lead in this corpus**: every `OverflowError` hit found
  (`pandas/15`, `17`, `75`, `76`, `93`) was `except (TypeError, ValueError, OverflowError)` added to
  an already-existing `except` clause inside pandas' `datetimelike`/`period`/JSON-parsing internals —
  none of them isolable without importing real pandas index types.
- **Searching against ESBMC's actual supported surface (`src/python-frontend/README.md` "Features
  Supported" / "Limitations" sections in the ESBMC repo, not this project's own docs) instead of
  against category keywords found `av_real_04`** (`luigi/9`): a pure bool/string logic bug in
  `execution_summary._partition_tasks`/`_summary_format` (a task that failed once and later
  succeeded on retry was still reported as `":("` because the buggy `failed` set was never narrowed
  by `- completed`). The whole buggy line sits inside booleans, string equality and `if`/`return` —
  all natively supported — so the harness reproduces the real function's control flow near-verbatim,
  no stub needed at all, unlike `none_misuse`'s assert-on-precondition workaround for unsupported
  `.decode()`/`None`-arithmetic. `PySnooper` (all 3 bugs: Python 2/3 encoding compat, frame
  introspection, custom-repr plumbing) was rejected wholesale — none of it is representable without
  `sys.settrace`/frame internals, entirely outside the frontend's scope. Of `luigi`'s other 32 bugs,
  most live inside `Scheduler`/`Worker`/`Task` state machines with heavy object-graph dependencies
  (`luigi/14`, `18`, `19` chain a `can_disable()`/`DISABLED`-state bug across three commits that
  would need a stubbed `Task`/`Failures` class pair to isolate correctly) — left as an open lead
  rather than rushed.
- **`tqdm/5` (the attribute-left-unset lead from the last pass) held up clean, no stub needed**:
  the real bug is pure control-flow ordering — `total = len(iterable)` is computed *after* the
  `if disable: return` early-return branch in the real `__init__`, so a disabled bar with an
  iterable but no explicit `total` silently keeps it unset. Reproduced as `av_real_05` with the
  real int/bool parameters unchanged (only the None-vs-set attribute state needed a bool flag,
  since ESBMC-Python has no None-typed int) — same near-verbatim shape as `av_real_04`.
- **`tqdm/9`'s SI-formatting rounding bug (`format_sizeof`) is real and dependency-free but not
  tractable within a normal timeout**: the bug (`abs(num) < 1000.0` lets a value like `9.996` round
  up to `"10.00"` when formatted to 2 decimals, breaking the format's fixed-width guarantee; fix
  moves the thresholds to `999.95`/`99.95`/`9.995`) reduces cleanly to a 2-branch float→string
  function, but ESBMC-Python's `__python_float_to_str` + `strlen` operational models are expensive
  enough under a symbolic float that `esbmc --z3 --unwind 6 --timeout 60s` still timed out (286
  VCCs, mostly bit-vector/floating-point encoding) even after narrowing the input range to a single
  branch. Rejected for this dataset, not for correctness — a candidate for `--incremental-bmc` with
  a much longer timeout or a narrower solver-level float encoding in a future pass, not a rushed
  abstraction.
- **`luigi/3`, `tqdm/3`, `pandas/73` scanned via a broader `TypeError`-keyword pass, all rejected**:
  `luigi/3` (`TupleParameter` catching `TypeError` alongside `ValueError` from `json.loads`) is
  isolable in principle but the actual crash depends on `json.loads`/`ast.literal_eval` semantics
  ESBMC-Python doesn't model, so faithfully triggering it would mean inventing the parse failure
  rather than reproducing it. `tqdm/3` (adding `__bool__` so `bool(tqdm_obj)` doesn't silently
  fall back to `__len__`) depends on Python's dunder-dispatch protocol for `bool()`, which isn't
  confirmed to be modeled by ESBMC-Python's `bool()` handling — needs a probe before it's worth
  building a harness around. `pandas/73` is `DataFrame` arithmetic dispatch over real `numpy`
  arrays (`ops.dispatch_to_series`, `mask_zero_div_zero`) — pandas-internal, same rejection shape
  as the rest of the pandas hits in this file.
- **Still no second `division_by_zero` case**: a fresh `grep` for zero-division patterns across all
  18 projects' patches (not just the original 3) surfaced only `pandas/73` as new, and it's the
  `DataFrame`-arithmetic rejection above, not an isolable zero-division. The category-scarcity
  finding above (2 candidates total in the whole corpus, only 1 usable) stands confirmed after a
  second, broader pass.

- **A 5th category, `type_mismatch`, from re-reading the `type_mismatch`/`other` triage candidates
  (`candidates_phase1.json`) end to end**: 3 of 7 held up as real, dependency-free logic bugs —
  `spacy/4` (CoNLL-U's `"_"` no-head sentinel reaching `int("_")`, real `ValueError`), `luigi/28`
  (Hive normalizes table names to lowercase but the caller's case-sensitive substring check missed
  real, differently-cased tables), `youtube-dl/1` (the `''` filter operator's `v is not None` check
  misclassifies a real `False` boolean field as "present"). The other 4 are clean rejections tied to
  specific, now-confirmed frontend gaps rather than category mismatches: `scrapy/23`
  (`'Basic ' + creds` bytes/str concat) looked like a real `TypeError` by grep, but ESBMC-Python
  treats `bytes` as `str` under the hood — the harness's `VERIFICATION FAILED` at low `--unwind`
  turned out to be an unwinding-bound artifact of `__python_str_concat`'s internal loop, not the real
  bug; it flips to `VERIFICATION SUCCESSFUL` at `--unwind 200`, confirming ESBMC-Python never raises
  the real `TypeError` here at all. `PySnooper/3` (`open(output_path, ...)` referencing an undefined
  name) fails at conversion time (`ERROR: NameError: name 'open' is not defined` — file I/O isn't
  modeled at all), not as a `VERIFICATION FAILED`/VCC counterexample, so it can't fit this schema
  regardless of stubbing. `youtube-dl/11` (`str_to_int` assuming its argument is always `str` or
  `None`) needs `re.sub`, which isn't modeled (only `match`/`search`/`fullmatch` are, confirmed by
  `esbmc`: `Unsupported function 'sub' is reached`), and reproducing the actual mistyped-argument
  crash without it runs into ESBMC-Python's limited `Union`/`Any` type support. `youtube-dl/6`
  (`parse_dfxp_time_expr` returning `0.0` vs `None`) turned out to be a compound bug once read in
  full — the real crash is a `KeyError` on `para.attrib['begin']`, not a type-mismatch at all, a
  category-mismatch trap the same shape as `thefuck/15`/`scrapy/18` already in this file.

- **A 6th category, `invalid_precondition`, from re-triaging the `invalid_precondition` slice of
  `candidates_phase1.json` (15 candidates)**: 9 held up as real, dependency-free logic bugs, all
  modeled as a `buggy_*`/`correct_*` sibling-function pair (the real buggy condition vs. the real
  fixed one) so ESBMC finds the exact input where they disagree, rather than a single function
  compared against a hand-picked constant. `scrapy/37` (URL scheme check too loose, `':' not in url`
  lets a Windows path slip through unflagged), `tornado/14` (inverted `is None`/`is not None` guard
  on `IOLoop.current()`), `scrapy/12` (missing mutual-exclusivity check on `Selector.__init__`'s
  `response`/`text` args), `tornado/2` (chunked-encoding check missed the case where
  `Transfer-Encoding` is already explicitly `"chunked"`), `ansible/2` (`__gt__ = not self.__lt__`
  is also true on equality, i.e. `a > a` wrongly holds), `pandas/38` (`_unstack_multiple`'s list
  comprehension compares against a stale loop variable `i` instead of the current `val`), `sanic/3`
  (`url_for`'s netloc ignored a `host` segment embedded in the route URI), `ansible/7`
  (`generate_commands` emitted a removal command for a key even when that key was also being
  re-set in the same run). `youtube-dl/28` (`_htmlentity_transform`'s `compat_chr()` call, uncaught,
  crashes on an out-of-range numeric HTML entity) is the near-verbatim standout of the batch: no
  `buggy_*`/`correct_*` pair needed at all, ESBMC-Python's own `chr()` operational model
  (`src/c2goto/library/python/string.c`) already enforces the real Unicode range and raises the
  exact property `chr() arg not in range(0x110000)`, so the real bug reproduces directly. One ESBMC
  8.3.0 internal crash found and worked around: a symbolic list literal (`[v0, v1]`) built inline
  inside a `for` loop with a `list[int]` return type aborts with `terminate called after throwing an
  instance of 'type2t::symbolic_type_excp'` — `pandas/38`'s harness reduces to a single-element
  scalar core instead of an actual list to route around it (same bug shape, no list needed). 6 of
  the 15 triaged candidates were left out of this batch, not rejected on correctness grounds:
  `thefuck/11`'s `is not -1` identity check is a real anti-pattern but not a provable bug for
  literal `-1` specifically (CPython's small-int cache makes `is`/`==` agree in that exact range,
  so there's no counterexample to find); `tqdm/3`, `tqdm/9`, `luigi/30`, `keras/28`, `spacy/7`
  need, respectively, a dunder-dispatch probe, a solver-performance retry (both already flagged
  above from the `assertion_violation` pass), a `Task`/status state-machine stub, and either a
  `numpy`-arithmetic stub or `set()`/`sorted()`-with-key modeling ESBMC-Python doesn't have — left
  as open leads for a future pass rather than rushed into a shaky abstraction.

- **`none_misuse` re-triaged from `candidates_phase1.json`'s 15-candidate slice, re-reading each
  patch in full rather than trusting the phase-1 label**: 7 of 15 held up, more than doubling the
  category. Two phase-1 labels flipped on close reading and were rejected outright:
  `fastapi/13` isn't a None crash at all — the pre-fix code already guards `if responses is None:
  responses = {}` inside the loop, and the real bug is a cumulative dict-merge aliasing issue
  across routes (out of scope for this category); `thefuck/26`'s pre-fix default was `machine = ""`,
  not `None` — no crash, a wrong-output bug about the "start all instances" case. `matplotlib/25`,
  `keras/30`, `pandas/86` were rejected for the usual numpy/pandas-internal coupling
  (`np.array`/`.ndim`, tensor `.shape`, `DataFrame` reshape internals). `black/4` is a real bug
  but produces a *wrong value* (a negative empty-line count), not a crash/exception — doesn't fit
  this category's assert-on-crash shape without more context on `_maybe_empty_lines` than the patch
  alone gives. Of the 7 accepted — `youtube-dl/39` (`nm_real_03`, `len(None)` on an unfound HTML
  caption span), `scrapy/1` (`nm_real_04`, `re.match()` on a `None` entry in `allowed_domains`),
  `scrapy/5` (`nm_real_05`, `Response.follow(url=None)` reaching `urljoin` unguarded), `scrapy/36`
  (`nm_real_06`, `create_instance()` returning `None` silently instead of raising `TypeError`),
  `tornado/9` (`nm_real_07`, `url_concat`'s missing `args is None` guard), `sanic/4` (`nm_real_08`,
  `self.app.config.SERVER_NAME` accessed without an `AttributeError` guard on a dynamic config
  object), `tqdm/6` (`nm_real_09`, `self.total` read before `__init__` ever assigns it, distinct
  from `nm_real_02`'s already-`None` case in the same file) — only `nm_real_03` reproduces via the
  real operation (`len()` on a NULL string, confirmed as `dereference failure: NULL pointer` /
  `CWE-476` in ESBMC's `strlen`); the other 6 use the assert-on-precondition technique, including
  `nm_real_04` where the real `re.match()` call was tried first and dropped only after testing
  showed it doesn't reliably raise once the `None` value crosses a function-parameter boundary in
  this shape (worth a closer look in a future pass — it may be an ESBMC-Python None-propagation gap
  specific to the re-module path, not a fundamental limit).
- **Ternary `x if cond else None` does not preserve NULL-pointer semantics for a str-annotated
  variable, but an `if`/`else` assignment does**: found while building `nm_real_03`. A minimal
  repro (`x: str = "hi" if has_title else None; len(x)`) verifies `SUCCESSFUL` — the real
  `len(NULL)` crash goes undetected — while the equivalent `if not has_title: x = None` form
  correctly verifies `FAILED` with the NULL-pointer counterexample. Worth flagging for
  `esbmc-python-guide`: prefer `if`/`else` over a ternary whenever a branch assigns `None` to an
  otherwise-typed variable.
- **`candidates_phase1.json`'s "high confidence" tag still needs a full-patch re-read before
  writing a harness**: of 19 high-confidence candidates re-examined for this batch, only 8 held up
  cleanly (`nm_real_10..12`, `tm_real_04..06`, `ip_real_10..11`). Rejects: `thefuck/26` was a
  feature commit (adds a "start all instances" fallback), not a crash fix, mislabeled by triage;
  `tqdm/9`'s rounding-boundary bug is the same solver-cost issue already logged above, not
  re-attempted; `matplotlib/25`, `keras/28`, `pandas/86`, `matplotlib/27`, `ansible/15`,
  `tornado/3`, `tornado/4` all needed either more surrounding context than the diff hunk alone
  gives (a downstream consumer, a numpy/random call, a weakref-cache identity check) or turned out
  to be a wrong-value bug too entangled with unmodeled state to isolate cleanly in the time
  available — left as open leads, not confirmed rejections. `thefuck/11` (`is not -1` identity
  compare on ints) was deprioritized, not rejected: worth a dedicated look at whether ESBMC-Python
  models `is` on int literals the way CPython's small-int cache does, since that's a genuinely
  interesting semantic question, not just a stub problem.
- **`assertion_violation`/`out_of_bounds` batch (6 av + 2 oob, all confirmed, 8/8)**: this pass
  targeted the highest-confidence leftover candidates from `candidates_phase1.json` and every one
  held up. Two (`oob_real_04` thefuck/22, `oob_real_05` black/17) are verbatim -- the real buggy line
  copied as-is, no abstraction at all, just an empty list/string literal to trigger the native
  IndexError check. The rest (`av_real_06`-`av_real_11`: thefuck/31, thefuck/32, thefuck/29,
  matplotlib/24, black/10, tornado/11) use the buggy-function/correct-function pair pattern --
  reproduce the real buggy logic and the real fixed logic side by side, assert they agree, let ESBMC
  find the input where they diverge. `matplotlib/24` needed one adjustment: ESBMC-Python's `max()`/
  `min()` are 2-argument only (no 3-arg or iterable form, per `src/python-frontend/README.md`
  Limitations), so the real `max(vmin, vmax, oldmax)` became nested `max(max(vmin, vmax), oldmax)`,
  semantically identical.
- **`invalid_precondition`/`none_misuse`/`type_mismatch` cleanup batch (5 confirmed: `ip_real_12`
  ansible/15, `ip_real_13` tornado/4, `ip_real_14` keras/28, `nm_real_13` tornado/3, `tm_real_07`
  matplotlib/3)**: all five are pure bool/int-arithmetic bugs with zero numpy/tensor/object
  dependency once isolated, modeled as buggy-function/correct-function pairs. `ip_real_14`
  (keras/28) is notable: `int(np.ceil(x/y))` drops the numpy dependency entirely via the equivalent
  integer identity `(x+y-1)//y`, so a bug that looked numpy-bound in the raw patch turned out fully
  isolable. Explicitly deferred (not rejected, just harder than the time budget allowed):
  `thefuck/11` (`is not -1` isn't actually the crux -- the real bug is in `replace_argument`/
  `command.script_parts` reconstruction logic, needs more stubbing than a quick pass supports),
  `matplotlib/25` and `pandas/86` (the None-check itself is trivial but the observable crash lives
  several calls deeper in numpy/pandas internals not shown in the diff hunk), `matplotlib/27`
  (hits ESBMC-Python's Any-type limitation: a function that can return either `int` or `str` isn't
  representable, per README's Any Type Limitations).

- `ip_real_18` (croniter, `expand_from_start_time`), `ip_real_19` (python-semver,
  `VersionInfo.__getitem__`), `ip_real_20` (watchdog, `generate_sub_moved_events`), `ip_real_21`
  (sortedcontainers, `SortedDict.__eq__`), `ip_real_22` (thefuck/18, `sudo.match`): five more
  `invalid_precondition` items from a mixed BugsInPy + fresh-GitHub-mining candidate batch. `ip_real_20`
  is a clean wrong-*value* case (not a crash): `str.replace()` replacing every occurrence of a
  directory-name prefix instead of just the leading one, reproduced with a concrete literal string
  where the prefix recurs deeper in the path (matches real issue #1158's own corrupting example).
  `ip_real_21` is the first item in this dataset where ESBMC's dict-subscript-on-missing-key model
  surfaces as an array-bounds violation (CWE-125) rather than a Python-level exception name -- same
  real bug (`KeyError` on an unguarded `that[key]`), just note the CWE framing if grepping by
  `expected_type`. `ip_real_22` needed `--unwind 30`, not the dataset's usual 6, because the
  counterexample search runs through `str.lower()`'s own internal per-character unwind loop --
  a reminder that a "no counterexample at unwind 6" result on a string-heavy harness can be an
  unwind-bound artifact, not a real absence of divergence; always bump the unwind and retry once
  before concluding a candidate doesn't verify. Dropped from this batch: `thefuck/11` (already
  deferred, confirmed on a second look that the real bug is deeper in `replace_argument`, not
  representable as isolated `is -1` logic since `-1 is -1` is reliably true in CPython anyway --
  not an identity-comparison bug in practice), `tqdm/9` (previously documented as too expensive for
  the float-to-string operational model, ~286 VCC and a 60s timeout on an earlier attempt --
  skipped rather than re-burning budget), `art`/`tsave` (needs `filename[::-1]`, and string
  slicing with a step is an explicit, documented ESBMC-Python limitation), `luigi/30` (real bug is
  a `try/finally` exception-vs-normal-completion distinction entangled with `Task`/logger/event
  side effects -- not reducible to scalar logic without stubbing away the actual mechanism being
  tested), `thefuck/30` (needs a regex match object's `.group()`, explicitly unsupported --
  match objects are boolean/None-testable only per this repo's `src/python-frontend/README.md`).

## Status

106 items total, by primary category (recount taken directly from `ground_truths.json`, the sole
authoritative source): 4 division_by_zero, 13 out_of_bounds, 19 assertion_violation, 23 none_misuse,
10 type_mismatch, 31 invalid_precondition, 2 variable_misuse, 1 integer_overflow, 3 incorrect_result.
Layout is flat (`bugs/*.py` + `detection/*.py` + one `ground_truths.json` with a `categories` list
per item) rather than one folder/file per category.

Went 105 → 100 in an earlier pass (5 pairs found to be the exact same real bug mined twice under
different IDs, deduplicated), then 100 → 103 adding a new source (ESBMC's own history, see below),
then 103 → 105 with a stricter issue-linked pass, and 105 → 106 with `dz_real_04`
(see "Human-validated sources" below).

**Human-validated sources.** Fernanda asked for the provenance breakdown to be explicit: of the
106 items, 76 come from BugsInPy (peer-reviewed academic curation — Widyasari et al., ESEC/FSE
2020), 16 from fresh GitHub mining where the fix commit references a real issue number (someone
external reported the bug before the fix — `issue_ref` is set in `provenance` for these), 3 from
ESBMC's own history (real commits, real regressions, but internal — no external reporter), and 11
accepted on commit-message-and-diff reading alone (no independent human confirmation beyond the
mining agent's own judgment — these are the ones a stricter future pass should either upgrade with
a found issue reference or flag with lower confidence in any citation of "N human-validated bugs").
The 2 newest issue-linked items: `ir_real_05` (shortuuid, wrong decode radix when `alphabet_index`
is passed, issue #115) and `nm_real_23` (python-markdown2, `TypeError` on `tag in
html_classes_from_tag` when that's explicitly `None`, issue #391). A third candidate this pass,
`humanize`'s `apnumber(0)` off-by-one (issue #72), triggered a live ESBMC crash on tuple-of-string
indexing (`compute_pointer_offset, unexpected irep`) and was dropped from the dataset — a real
ESBMC bug worth its own report, not a dataset defect.

**New source: ESBMC's own git history (`incorrect_result`, 3 items).** `src/python-frontend/models/*.py`
is real Python source too, and its own fix history has genuine wrong-result bugs, not just BugsInPy/GitHub
projects: `ir_real_01`/`ir_real_02` are the `math.gamma`/`lgamma` Lanczos branch and the module-level
`pi`/`e`/`tau` constants both using a hand-typed, imprecise `pi_const` before #5963/#3583 fixed them;
`ir_real_03` is `re.py`'s `[x-y]+`/`[x-y]*` recognizer checking `pattern_len != 7` (off-by-one — a real
6-character pattern like `[a-z]+` never matches) before #d8ad5349c1. None of these crash or raise; they're
"incorrect_result" because ESBMC silently computed/verified the wrong value, closer to `assertion_violation`'s
shape than to a crash-category, but the property being violated is a real mathematical/string-length fact,
not a project-specific precondition, hence the new category label. `provenance.project == "esbmc"` for all
three, distinguishing them from the BugsInPy/GitHub-sourced items.

Two other ESBMC-history candidates were tried and dropped, not because they were false — because the
underlying frontend gap has since been fixed by unrelated later work, so they no longer reproduce on the
current build: `int.from_bytes(signed=True)`'s negative-indexing crash (negative list indexing is now
supported) and `random.randrange`'s `None`-as-`0` confusion (None now has proper type distinction from
int per this repo's `src/python-frontend/README.md`). A third, `int.from_bytes`'s wrong-byte-for-big-endian
value bug once the crash was worked around, hit an unrelated live Z3 encoding crash (`Sorts
struct_type_pointer_struct and (_ BitVec 64) are incompatible`) — worth a `esbmc-verifier`-style report on
its own, not folded into this dataset.

**Final cleanup pass over `candidates_phase1.json`'s last ~23 unresolved candidates**: 7 confirmed
-- `oob_real_15` (youtube-dl/6, near-verbatim `dict['begin']` KeyError vs. the fixed `.get()`),
`oob_real_16` (boltons `IndexedSet` double negative-index normalization silently wrapping an
out-of-range index instead of raising), `av_real_21` (youtube-dl/18, force_properties filter tuple
missing 3 keys that then leaked through), `ip_real_31` (matplotlib/26, swapped `oldmin`/`oldmax` in
an axis-limit `max()`/`min()` call), `ip_real_32` (parse.py PM-hour `+12` overflow past 23, GitHub
issue #16, modeled as pure int arithmetic rather than through the datetime OM), `ip_real_33`
(send2trash empty-path-list not short-circuited before the Windows batch-delete pipeline, issue
#71), `tm_real_10` (luigi/1, `metrics.configure_http_handler()` called on the wrong object --
AttributeError, modeled with two minimal classes).

Two more real **ESBMC-Python limitations confirmed by direct probe** (not dataset items):
- `cachetools`'s `__get__`-on-`obj=None` bug needs the descriptor protocol; a minimal probe
  (`Owner().d` where `d` is a `__get__`-defining class attribute) crashes with `Z3 error: Sorts
  struct_type_Descriptor and (_ BitVec 64) are incompatible` -- ESBMC-Python does not invoke
  `__get__` on attribute access, it treats the class attribute as a plain struct value. A real
  frontend gap, not a false candidate.
- `arrow`'s 32-bit `datetime.timestamp()` overflow candidate: confirmed by grepping
  `src/python-frontend/models/datetime.py` that `timestamp()` isn't modeled at all yet, so the bug
  isn't representable in any form, not even a probe-shaped harness.

Remaining candidates in `candidates_phase1.json` not promoted to `ground_truths/`: `thefuck/11`,
`tqdm/3`, `tqdm/9`, `luigi/30`, `scrapy/23`, `luigi/13`, `thefuck/30`, `luigi/25`, `scrapy/21`,
`spacy/2` (blocked on the `dict.update()` ESBMC bug itself, not a triage rejection), `boltons`
`math.log(x, 1.0)` (solver-cost reject, ~60s timeout even reduced), `deepdiff`'s two candidates
(one is a conversion-time error not a VCC, the other's `VERIFICATION FAILED` was a false positive
inside the C string OM's `strlen`, same artifact class as `scrapy/23`) -- each already has a
concrete reason recorded in this file's earlier Findings entries or in this pass. This is a
reasonable stopping point: everything left has either a real ESBMC limitation blocking it, a
confirmed-not-a-bug verdict, or a cost/complexity reason not worth forcing.

**Batch added by this pass** (out_of_bounds/assertion_violation/invalid_precondition/integer_overflow
scope): 19 new confirmed items -- 6 out_of_bounds (`oob_real_09..14`: dateutil off-by-one bound,
python-tabulate empty-list `[0]`, wcwidth unclamped loop end, natsort `x[0]` on empty string, emoji
ZWJ-branch double unguarded index, distro `lines[0]` on empty uname output), 5 assertion_violation
(`av_real_14,15,17,19,20`: thefuck `open` rule slice-vs-replace divergence, scrapy gunzip
`extrabuf[-extrasize:]` truncation, youtube-dl `unified_strdate` None-vs-"None"-string, matplotlib
axis limit min/max arg swap, black tab-vs-space column-width merge), 8 invalid_precondition
(`ip_real_23..30`: luigi significant-param filter, luigi assistant/workers truthiness, luigi
DONE/DISABLED/UNKNOWN membership, luigi re-schedule worker-mismatch guard, tornado
Transfer-Encoding-chunked check, tornado inverted `is None` current-loop guard, keras
`TimeseriesGenerator.__len__` off-by-one -- modeled with `math.ceil` over plain ints, no numpy
needed -- and tornado HTTP range `start>=end` validity check). `integer_overflow` stays empty this
pass (the one open candidate, `arrow`'s platform-dependent timestamp overflow, still needs a probe
of ESBMC's datetime word width before it's worth building).

Two new **live ESBMC bugs** surfaced while building this batch, not dataset items:
- `av_real_16` (luigi/spacy-style `dict.update()` harness) hit a **20s timeout at 17227 VCCs** even
  for a 2-key dict -- consistent with the `dict.update()`-not-overwriting-a-key anomaly a sibling
  fork already flagged; the cost explosion is worth investigating alongside that.
- `av_real_18` (youtube-dl `for f in (...): if f in d: del d[f]` over a 6-string tuple) crashed
  ESBMC itself: `terminate called after throwing an instance of 'irep2_cast_error' ... to_array_type()
  called on type whose type_id is struct`. Reproducible with `esbmc av_real_18.py --z3 --unwind 6`
  before this pass deleted the file (recoverable from this note + the diff in `bug_patch.txt` for
  `youtube-dl` bug 18 if someone wants to file it).

Deferred (not rejected) from this pass's scope, for a future round: `thefuck/11` (real bug is
deeper in `replace_argument`, not the `is -1` line, per an earlier pass's note -- still unresolved),
`tqdm/9` (already-documented solver-expensive rounding bug), `luigi/30` (try/finally restructure
entangled with Task/logger side effects, not cleanly scalar-isolable), `thefuck/30` (needs a regex
match object's `.group()`, unsupported), `tqdm/3` (`__bool__` dunder-dispatch question, needs a
live probe), `matplotlib/26` (same max/min-swap shape as `av_real_19`/`matplotlib/24`, likely a
near-duplicate bug ID -- worth a diff check against `av_real_19` before building rather than
assuming duplicate).

**RESOLVED -- data-loss incident from a prior parallel round:** a fork had reused
`ip_real_15`/`16`/`17.py` for new content without checking they already existed, overwriting the
real `black/4`, `pandas/86`, and `scrapy/17` harnesses. The coordinator regenerated all three from
`ground_truths/invalid_precondition.json`'s surviving metadata (function name, expression,
provenance, abstraction_notes) and reverified each with `esbmc --z3 --unwind 6` --
`VERIFICATION FAILED` with VCC>0 on all three, matching the original entries. Root cause stands as
a lesson for future parallel passes: concurrent forks writing the same category file need to check
`ls bugs/<category>/` fresh immediately before writing, not rely on a next-ID number computed at
task start.

- `ip_real_15` (black/4), `ip_real_16` (pandas/86), `ip_real_17` (scrapy/17), `nm_real_14`
  (scrapy/29): four more buggy/correct-pair or explicit-precondition items, none needing
  project-internal types -- `before -= previous_after` unguarded on the first line, `pivot
  (columns=None)` silently accepted instead of raising, `dict.get()` with no default for
  unknown HTTP status codes, and `to_bytes(hostname)` on a netloc-less URL's `None` hostname.

Candidate-hunting
is labor-intensive by hand — reading each fix patch in full to reject category mismatches took most
of the time, not writing the harnesses; the `none_misuse` pair took reading roughly 25 patches across
9 new projects (httpie, sanic, ansible, tqdm, cookiecutter, fastapi, scrapy, spacy, keras) to find 2
that held up, and `av_real_04`/`av_real_05` took reading 3 PySnooper patches, a scan of `luigi`'s 33,
and the `tqdm`/`luigi`/`pandas` leads listed above to find 2 more clean, no-stub candidates. Next
batch: a second genuinely clean `division_by_zero` case still hasn't turned up anywhere in BugsInPy
after two passes — may need to accept 1 is what this corpus has, or widen past BugsInPy entirely;
`tqdm/9` needs a solver-performance retry (longer timeout or narrower float encoding), not a logic
fix; `tqdm/3`'s `__bool__`-dispatch dependency needs a quick probe of whether ESBMC-Python's `bool()`
follows Python's dunder protocol before it's worth pursuing; and the `luigi/14`+`18`+`19`
`can_disable()`/`DISABLED`-state chain still needs a stubbed `Task` object, not a straight scalar
reduction.

- **Batch A verification pass (`none_misuse`/`type_mismatch`/`variable_misuse`/`division_by_zero`
  scope)**: +10 confirmed (`nm_real_15`..`nm_real_22`, `tm_real_08`, `tm_real_09`). Two BugsInPy
  candidates verified cleanly: `fastapi/13` (a router-level `responses` dict wrongly reassigned
  inside a route loop, leaking one route's response codes into the next) and `matplotlib/5`
  (unconditional linewidth overwrite instead of a None-only substitution). Six fresh-GitHub
  candidates (`python-tabulate` x3, `tenacity`, `voluptuous`, `inflect`, `jmespath.py`,
  `python-dotenv`) all confirmed on the first try using the established bool-precondition-assert
  pattern (`nm_real_01`/`02` style).
  Three rejected on genuine ESBMC-Python limitations, not abstraction failure: `luigi/25`
  (calling a `@property`-decorated attribute as a function produces no checkable counterexample --
  `VERIFICATION SUCCESSFUL`, 0 VCC, ESBMC does not reject calling a `str` as a function); `schema`'s
  `'%r' % k` tuple-vs-scalar bug (0 VCC -- the `%` operator isn't modeled to reproduce Python's real
  tuple-unpacking-into-multiple-args semantics); `deepdiff`'s `list.append(x, y)` two-positional-arg
  bug (fails at conversion time -- `ERROR: append() takes exactly one argument` -- not a runtime
  VCC). One rejected as a **false positive**, same shape as the `scrapy/23` finding: `deepdiff`'s
  `len(other.indexes > 1)` (list > int comparison) does produce `VERIFICATION FAILED`, but the
  violated property traces into `strlen` inside the C string operational model, not a real
  TypeError. `cachetools`'s `__get__` descriptor-protocol bug dropped without a probe run
  (automatic `__get__` dispatch via attribute access isn't in ESBMC-Python's documented feature
  list, and CPython's descriptor protocol requires exactly that dispatch to trigger). `scrapy/21`
  dropped: the real bug is a Twisted-Deferred reentrant-callback race, not scalar logic.
