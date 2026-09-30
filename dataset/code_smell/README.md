# External Python Code Smell Dataset

Code smells in Python taken from external sources that already label and categorise them. Kept apart from the V1 smell controls (`dataset/labeled/`) and from V2, so importing it changes no reported V1 or V2 number. Smells are maintainability findings: nothing here goes to ESBMC.

Rebuild with `python scripts/build_code_smell_dataset.py` (downloads the labels and the project sources; `summary.json` is regenerated).

## Sources

| Source | Smells | Label origin | Code | Licence |
|---|---|---|---|---|
| PySmell, [chenzhifei731/Pysmell](https://github.com/chenzhifei731/Pysmell) at commit `233afeb`, folder `detection/example repository/manual inspection` | 10 general Python smells | `manual analysis` column: human inspection, positives and negatives | 9 real projects at pinned tags, fetched from GitHub | Repository ships no licence; each snippet keeps its project's licence (see `source_url`) |
| SpecDetect4AI replication package, public mirror [KamruzzamanAsif/SpecDetect4AI-B903](https://github.com/KamruzzamanAsif/SpecDetect4AI-B903) at commit `7576762` of the anonymous artifact `SpecDetect4AI-B903` cited by the paper | 22 ML-specific smells (catalogue at [hynn01.github.io/ml-smells](https://hynn01.github.io/ml-smells/)) | mlflow: three annotators, blind two-pass protocol, consensus on disagreement. CodeSmile: 100 files re-annotated by the same annotators and adjudicated | mlflow fork [PeterHamfelt/mlflow](https://github.com/PeterHamfelt/mlflow) at commit `7a688bf` (the snapshot annotated); CodeSmile files shipped in the package | mlflow: Apache-2.0. Package and CodeSmile files: no licence stated |
| Smelly Code Dataset, Zenodo [10.5281/zenodo.14989674](https://doi.org/10.5281/zenodo.14989674), Python part | 21 Fowler-style smells | Comments written by the author in code written to be smelly | 7 files vendored in `smelly_code/` | MIT (`smelly_code/LICENSE`) |

## Files

| File | Items | Positives | Negatives | Granularity |
|---|---|---|---|---|
| `pysmell_manual.jsonl` | 2570 | 150 | 2420 | line of a def, class or expression |
| `mlflow_ml_smells.jsonl` | 410 | 214 | 196 | line for positives; whole file for negatives (file annotated, none of the 22 smells) |
| `codesmile_ml_smells.jsonl` | 376 | 240 | 136 | line |
| `smelly_code_labels.json` | 132 | 132 | 0 | method or class |

`files/<smell>/<id>.py` holds the code itself: one file per enclosing function or class that a human marked as smelly, only where the location was confirmed (PySmell `verified`/`file_verified`, mlflow `unverified`, CodeSmile `verified`). Each file starts with a comment header naming the smell, who validated it, the origin URL with line range, and the smelly line numbers both in the original file and in the file itself. 379 files over 24 smells: 60 from PySmell, 178 from mlflow and 141 from CodeSmile (labels on the same function are merged into one file). Negatives and unconfirmed positives stay only in the JSONL files. `smelly_code/` holds the annotated Smelly Code files unchanged. `summary.json` has the counts per smell, per location status and per V1 threshold outcome.

Common fields: `smell` (name used by the source), `label` (1 smelly, 0 not), `path`, `line`, `source_url`, `location`, `line_text`, `snippet` (the enclosing function or class, cut by indentation). ML items add `rule` (R1 to R22); CodeSmile items add `review`, the adjudicated outcome (`True_Positive` and `False_Negative` are smells, `True_Negative` is not). PySmell and Smelly items add `category_v1` (`long_method`, `many_parameters` or null when V1 has no such category), `v1_measures` and `meets_v1_threshold` (the V1 policy from `src/research_pipeline/config/smell_thresholds.json` applied to the same function; null when the code does not parse as Python 3). PySmell items also carry the original metrics and the two PySmell tool heuristics.

## Location check

The labels point at a file and line of a code base the annotators saw; `location` says how far that pointer was confirmed against the code fetched here.

| `location` | Meaning | PySmell (pos.) | mlflow (pos.) | CodeSmile (pos.) |
|---|---|---|---|---|
| `verified` | PySmell: def/class smell on a `def`/`class` line. CodeSmile: line text equals the code context stored with the label | 787 (31) | | 354 (240) |
| `file_verified` | PySmell expression smell in a file whose def/class labels are all `verified` | 323 (29) | | |
| `unverified` | Line exists and holds code, nothing more to check | 1001 (67) | 211 (211) | |
| `file` | File-level negative | | 196 (0) | |
| `mismatch` | Line out of range, blank or not a `def`/`class` line; snippet dropped | 415 (13) | 3 (3) | |
| `not_fetched` | Code not available: file missing at the tag (PySmell), or the package folder holds a different file than the one labelled (CodeSmile) | 44 (10) | | 22 (0) |

PySmell analysed revisions close to, but not always equal to, the tags on GitHub (offsets of 1 to 41 lines in a sample; 301 of its 415 mismatches are Django or Matplotlib). The mlflow lines are `unverified` only because the labels carry no code to compare with: 14 of 14 randomly sampled lines hold exactly the construct their smell names. Use `verified` and `file_verified` (and mlflow `unverified`) when the snippet must be the labelled code.

## Caveats

- The ML smells are a different taxonomy from V1: none maps to `long_method`, `many_parameters` or `complex_conditional`.
- The SpecDetect4AI paper reports 387 ground-truth instances for mlflow; the published spreadsheet holds 214 labelled lines. The difference is not explained in the package.
- The SpecDetect4AI mirror is a third-party copy of the anonymous artifact; its content matches the paper's description (241 mlflow files, 22 rules, 100 CodeSmile files) but it is not published by the authors.
- PySmell and Smelly labels disagree with the V1 thresholds. PySmell's Long Parameter List positives start at 4 parameters counting `self`; V1 needs 5 without it. Of the 31 PySmell `many_parameters` positives, 7 meet the V1 threshold, 15 do not and 9 could not be measured. Of the 5 Smelly "Long Method" methods only one reaches 16 executable lines, and two of its "Long Parameter List" methods take no parameters at all.
- The Smelly Code files were written to contain smells and were labelled only by their author. Cashier, Chef, Customer, Pizza and Shop repeat the same blocks, so distinct examples are far fewer than 132, and several labels do not match their code (for example "Message Chain" on a single call). Most of its smells are class-level and need the whole file as context.
- The PySmell projects are Python 2 era. Snippets are cut by indentation, so they exist for every located item, while V1 measurements need a Python 3 parse.
