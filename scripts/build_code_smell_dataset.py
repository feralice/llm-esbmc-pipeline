"""Build dataset/code_smell/ from externally validated Python code smell sources.

Sources, kept apart from the V1 controls (dataset/v1_sintetico) and from V2:

* PySmell (Chen et al.): the "manual inspection" CSVs carry a human label per
  (project, tag, file, line). The source is not shipped with PySmell, so each
  file is fetched from GitHub at the pinned project tag and the labelled
  function, class or statement is cut out by indentation (the projects are
  Python 2 era, so AST parsing is only attempted for the V1 measurements).
* Smelly Code Dataset (Zenodo 14989674): smells annotated by the author as
  comments; the files are vendored under smelly_code/ and labels are read
  from those comments.
* SpecDetect4AI replication package (public mirror of the anonymous artifact):
  line-level human labels of the 22 ML-specific smells of Zhang et al. on
  241 mlflow files, fetched from the mlflow fork the authors analysed, and
  the adjudicated re-annotation of CodeSmile's 100 validation files, which
  the package ships.

Writes pysmell_manual.jsonl, smelly_code_labels.json, mlflow_ml_smells.jsonl,
codesmile_ml_smells.jsonl and summary.json.
"""

from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import re
import shutil
import sys
import textwrap
import warnings
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from urllib import error, parse, request
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.preprocess import _all_arg_nodes
from research_pipeline.smell_policy import (
    load_smell_thresholds,
    smell_measurements,
)

PYSMELL_COMMIT = "233afebac24c910be89d065ffa661ec72458a62c"
PYSMELL_CSV_URL = (
    "https://raw.githubusercontent.com/chenzhifei731/Pysmell/"
    f"{PYSMELL_COMMIT}/pysmell/detection/example%20repository/manual%20inspection/{{}}.csv"
)
GITHUB_REPOS = {
    "ansible": "ansible/ansible",
    "boto": "boto/boto",
    "django": "django/django",
    "ipython": "ipython/ipython",
    "matplotlib": "matplotlib/matplotlib",
    "nltk": "nltk/nltk",
    "numpy": "numpy/numpy",
    "scipy": "scipy/scipy",
    "tornado": "tornadoweb/tornado",
}
PYSMELL_SMELLS = {
    "ComplexContainerComprehension": None,
    "LargeClass": None,
    "LongBaseClassList": None,
    "LongLambdaFunction": None,
    "LongMessageChain": None,
    "LongMethod": "long_method",
    "LongParameterList": "many_parameters",
    "LongScopeChaining": None,
    "LongTernaryConditionalExpression": None,
    "MultiplyNestedContainer": None,
}
DEFINITION_SMELLS = {"LargeClass", "LongBaseClassList", "LongMethod", "LongParameterList"}
LABEL_COLUMNS = {"subject", "tag", "file", "lineno", "experience-based", "statistics-based", "manual analysis"}

SPECDETECT_REPO = "KamruzzamanAsif/SpecDetect4AI-B903"
SPECDETECT_COMMIT = "7576762f92b4205c9a995082edb215474b4e40d0"
SPECDETECT_GT = "Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile"
MLFLOW_REPO = "PeterHamfelt/mlflow"
MLFLOW_COMMIT = "7a688bf4942c63608de91909aa4472ec1e6652b3"
ML_SMELLS = {
    "R1": "Broadcasting Feature Not Used",
    "R2": "Randomness Uncontrolled",
    "R3": "TensorArray Not Used",
    "R4": "Training / Evaluation Mode Improper Toggling",
    "R5": "Hyperparameter Not Explicitly Set",
    "R6": "Deterministic Algorithm Option Not Used",
    "R7": "Missing the Mask of Invalid Value",
    "R8": "PyTorch Call Method Misused",
    "R9": "Gradients Not Cleared Before Backward Propagation",
    "R10": "Memory Not Freed",
    "R11": "Data Leakage",
    "R12": "Matrix Multiplication API Misused",
    "R13": "Empty Column Misinitialization",
    "R14": "Dataframe Conversion API Misused",
    "R15": "Merge API Parameter Not Explicitly Set",
    "R16": "In-Place APIs Misused",
    "R17": "Unnecessary Iteration",
    "R18": "NaN Equivalence Comparison Misused",
    "R19": "Threshold-Dependent Validation",
    "R20": "Chain Indexing",
    "R21": "Columns and DataType Not Explicitly Set",
    "R22": "No Scaling Before Scaling-sensitive Operation",
}

SMELLY_SMELLS = {
    "Control Coupling": None,
    "Data Class": None,
    "Data Clumps": None,
    "Dead Code": None,
    "Divergent Change": None,
    "Duplicate Code": None,
    "Feature Envy": None,
    "Inappropriate Intimacy": None,
    "Lazy Class": None,
    "Long Method": "long_method",
    "Long Parameter List": "many_parameters",
    "Message Chain": None,
    "Middle Man": None,
    "Parallel Inheritance Hierarchies": None,
    "Primitive Obsession": None,
    "Refused Bequest": None,
    "Shotgun Surgery": None,
    "Speculative Generality": None,
    "Switch Statements": None,
    "Temporary Fields": None,
    "Unnecessary Comments": None,
}
SMELLY_COMMENT = re.compile(r"#\s*(?:More\s+|Dependency Injection \()?(" + "|".join(SMELLY_SMELLS) + r")")
HEADER = re.compile(r"\s*(?:async\s+)?(?:def|class)\s")


def _fetch(url: str) -> bytes | None:
    try:
        with request.urlopen(url, timeout=60) as response:
            return response.read()
    except error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _is_code(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def _block(lines: list[str], index: int) -> tuple[int, int, str]:
    """Return (start, end, kind) of the def/class enclosing lines[index], 0-based, end exclusive."""
    if HEADER.match(lines[index]):
        return index, _block_end(lines, index), _kind(lines[index])
    target_indent = _indent(lines[index])
    for header in range(index - 1, -1, -1):
        # A closer def at lower indent may be a sibling that already ended.
        if HEADER.match(lines[header]) and _indent(lines[header]) < target_indent:
            end = _block_end(lines, header)
            if end > index:
                return header, end, _kind(lines[header])
    return index, index + 1, "statement"


def _block_end(lines: list[str], header: int) -> int:
    header_indent = _indent(lines[header])
    end = next(
        (i for i in range(header + 1, len(lines))
         if _is_code(lines[i]) and _indent(lines[i]) <= header_indent
         and not lines[i].lstrip().startswith((")", "]", "}"))),
        len(lines),
    )
    while end > header + 1 and not _is_code(lines[end - 1]):
        end -= 1
    return end


def _kind(header_line: str) -> str:
    return "class" if header_line.lstrip().startswith("class") else "function"


def _v1_measures(source: str, line: int) -> dict | None:
    """Measure the function defined at `line` with the V1 smell policy; None if unparsable.

    The function is unparsed rather than dedented: docstrings flush with column 0
    break dedent, and unparse keeps one statement per line, which is what the
    policy counts (only `a; b` on one line would differ).
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == line:
            unit = SimpleNamespace(
                source=ast.unparse(node),
                parameters=[arg.arg for arg in _all_arg_nodes(node.args)],
            )
            return smell_measurements(unit)
    return None


def _meets_v1(category: str | None, measures: dict | None) -> bool | None:
    if category is None or measures is None:
        return None
    policy = load_smell_thresholds()
    if category == "long_method":
        return measures["executable_lines"] >= policy["long_method_min_executable_lines"]
    return measures["parameters"] >= policy["many_parameters_min"]


def _pysmell_rows() -> list[dict]:
    rows = []
    for smell in PYSMELL_SMELLS:
        text = _fetch(PYSMELL_CSV_URL.format(smell)).decode("utf-8", errors="replace")
        for row in csv.DictReader(io.StringIO(text)):
            path = re.search(r"subject_raw\\[^\\]+\\[^\\]+\\(.*)", row["file"]).group(1).replace("\\", "/")
            rows.append({"smell": smell, "path": path, **row})
    return rows


def _source_url(row: dict) -> str:
    repo = GITHUB_REPOS[row["subject"]]
    return f"https://raw.githubusercontent.com/{repo}/{parse.quote(row['tag'])}/{parse.quote(row['path'])}"


def _cached_source(url: str, cache: Path) -> str | None:
    target = cache / parse.urlparse(url).path.lstrip("/")
    if not target.exists():
        data = _fetch(url)
        if data is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return target.read_text(encoding="utf-8", errors="replace")


def build_pysmell(cache: Path) -> list[dict]:
    rows = _pysmell_rows()
    urls = sorted({_source_url(row) for row in rows})
    with ThreadPoolExecutor(max_workers=8) as pool:
        sources = dict(zip(urls, pool.map(lambda url: _cached_source(url, cache), urls)))

    items = []
    for number, row in enumerate(rows, start=1):
        url = _source_url(row)
        source = sources[url]
        line = int(row["lineno"])
        item = {
            "id": f"pysmell_{number:04d}",
            "source": "pysmell",
            "smell": row["smell"],
            "category_v1": PYSMELL_SMELLS[row["smell"]],
            "label": int(row["manual analysis"]),
            "tool_experience_based": int(row["experience-based"]),
            "tool_statistics_based": int(row["statistics-based"]),
            "metrics": {k: float(v) if v else None for k, v in row.items()
                        if k and k not in LABEL_COLUMNS | {"smell", "path"}},
            "project": row["subject"],
            "tag": row["tag"],
            "path": row["path"],
            "line": line,
            "source_url": url.replace("raw.githubusercontent.com", "github.com").replace(
                f"/{parse.quote(row['tag'])}/", f"/blob/{parse.quote(row['tag'])}/", 1) + f"#L{line}",
        }
        lines = source.splitlines() if source is not None else []
        if not lines:
            item["location"] = "not_fetched"
        elif not 1 <= line <= len(lines):
            item["location"] = "mismatch"
        elif row["smell"] in DEFINITION_SMELLS:
            item["location"] = "verified" if HEADER.match(lines[line - 1]) else "mismatch"
        else:
            item["location"] = "unverified"
        items.append((item, url, lines))

    # PySmell analysed a revision close to, but not always equal to, the tag; a
    # file whose def/class labels all land on a def/class line is taken as the same revision.
    checked: dict[str, set[str]] = {}
    for item, url, _ in items:
        if item["smell"] in DEFINITION_SMELLS and item["location"] in {"verified", "mismatch"}:
            checked.setdefault(url, set()).add(item["location"])
    for item, url, lines in items:
        if item["location"] == "unverified" and checked.get(url) == {"verified"}:
            item["location"] = "file_verified"
        if item["location"] in {"not_fetched", "mismatch"}:
            continue
        _add_snippet(item, lines)
        if item["category_v1"]:
            measures = _v1_measures("\n".join(lines), item["line"])
            item["v1_measures"] = measures
            item["meets_v1_threshold"] = _meets_v1(item["category_v1"], measures)
    return [item for item, _, _ in items]


def _raw_url(repo: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{parse.quote(path)}"


def _blob_url(repo: str, commit: str, path: str, line: int | None = None) -> str:
    return f"https://github.com/{repo}/blob/{commit}/{parse.quote(path)}" + (f"#L{line}" if line else "")


def _fetch_all(urls: set[str], cache: Path) -> dict[str, str | None]:
    urls = sorted(urls)
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(urls, pool.map(lambda url: _cached_source(url, cache), urls)))


def _add_snippet(item: dict, lines: list[str]) -> None:
    start, end, kind = _block(lines, item["line"] - 1)
    item.update(
        line_text=lines[item["line"] - 1].strip(),
        snippet_kind=kind,
        snippet_start=start + 1,
        snippet_end=end,
        snippet=textwrap.dedent("\n".join(lines[start:end])),
    )


def _xlsx_rows(data: bytes) -> list[list[str]]:
    """First sheet of an .xlsx as rows of strings; avoids an openpyxl dependency."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        shared = [
            "".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t"))
            for si in ElementTree.fromstring(book.read("xl/sharedStrings.xml")).findall("m:si", ns)
        ]
        sheet = ElementTree.fromstring(book.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.iter(f"{{{ns['m']}}}row"):
        cells: dict[int, str] = {}
        for cell in row.findall("m:c", ns):
            column = re.match(r"[A-Z]+", cell.get("r")).group(0)
            index = 0
            for char in column:
                index = index * 26 + ord(char) - 64
            value = cell.find("m:v", ns)
            text = "" if value is None else value.text or ""
            cells[index - 1] = shared[int(text)] if cell.get("t") == "s" else text
        rows.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
    return rows


def build_mlflow(cache: Path) -> list[dict]:
    """mlflow ground truth: one item per labelled line, one label-0 item per file with no smell."""
    sheet = _fetch(_raw_url(SPECDETECT_REPO, SPECDETECT_COMMIT,
                            "Evaluation/Comparison_Other_Tools/GroundTruth_Manual_Eval.xlsx"))
    header, *rows = _xlsx_rows(sheet)
    rules = [re.search(r"R\d+", column).group(0) for column in header[2:]]
    labelled = []
    for row in rows:
        path = row[0].split("mlflow-master/", 1)[1]
        lines = sorted({
            (rule, int(token))
            for rule, cell in zip(rules, row[2:])
            for token in re.split(r"[;,/\s]+", cell) if token.isdigit()
        })
        labelled.append((path, lines))
    sources = _fetch_all({_raw_url(MLFLOW_REPO, MLFLOW_COMMIT, path) for path, _ in labelled}, cache)

    items = []
    for path, lines in labelled:
        source = sources[_raw_url(MLFLOW_REPO, MLFLOW_COMMIT, path)]
        base = {"source": "specdetect4ai_mlflow", "project": "mlflow", "path": path}
        if not lines:
            items.append({**base, "smell": None, "rule": None, "label": 0, "granularity": "file",
                          "source_url": _blob_url(MLFLOW_REPO, MLFLOW_COMMIT, path),
                          "location": "not_fetched" if source is None else "file"})
            continue
        file_lines = source.splitlines() if source is not None else []
        for rule, line in lines:
            item = {**base, "smell": ML_SMELLS[rule], "rule": rule, "label": 1, "granularity": "line",
                    "line": line, "source_url": _blob_url(MLFLOW_REPO, MLFLOW_COMMIT, path, line)}
            if not file_lines:
                item["location"] = "not_fetched"
            elif not 1 <= line <= len(file_lines) or not _is_code(file_lines[line - 1]):
                item["location"] = "mismatch"
            else:
                item["location"] = "unverified"
                _add_snippet(item, file_lines)
            items.append(item)
    for number, item in enumerate(items, start=1):
        item["id"] = f"mlflow_{number:04d}"
    return items


def build_codesmile(cache: Path) -> list[dict]:
    """CodeSmile validation files re-annotated and adjudicated in the SpecDetect4AI package."""
    table = _fetch(_raw_url(SPECDETECT_REPO, SPECDETECT_COMMIT, f"{SPECDETECT_GT}/GT_CodeSmile_Reviewed.csv"))
    rows = list(csv.DictReader(io.StringIO(table.decode("utf-8")), delimiter=";"))
    tree = json.loads(_fetch(
        f"https://api.github.com/repos/{SPECDETECT_REPO}/git/trees/{SPECDETECT_COMMIT}?recursive=1"))
    kit_files = {
        entry["path"].split("/files/", 1)[1]: entry["path"]
        for entry in tree["tree"]
        if entry["path"].startswith(f"{SPECDETECT_GT}/CodeSmile-Validation/experimental_kits/")
        and entry["path"].endswith(".py")
    }
    sources = _fetch_all({_raw_url(SPECDETECT_REPO, SPECDETECT_COMMIT, p) for p in kit_files.values()}, cache)

    items = []
    for number, row in enumerate(rows, start=1):
        kit_path = kit_files.get(row["File"].removeprefix("./files/"))
        line = int(row["Line"])
        item = {
            "id": f"codesmile_{number:04d}",
            "source": "specdetect4ai_codesmile",
            "smell": ML_SMELLS[row["Rule_ID"]],
            "rule": row["Rule_ID"],
            # Old_Type is the tool's outcome before review; after it, the smell is present
            # exactly when the line is a true positive or a detection the tool missed.
            "label": int(row["New_Type"] in {"True_Positive", "False_Negative"}),
            "review": row["New_Type"],
            "path": row["File"].removeprefix("./files/"),
            "line": line,
            "granularity": "line",
        }
        source = sources.get(_raw_url(SPECDETECT_REPO, SPECDETECT_COMMIT, kit_path)) if kit_path else None
        if source is None:
            item["location"] = "not_fetched"
        else:
            lines = source.splitlines()
            context = re.search(rf"^{line}:(.*)$", row["Code_Context"], re.MULTILINE)
            matches = context and line <= len(lines) and context.group(1).strip() == lines[line - 1].strip()
            item["location"] = "verified" if matches else "mismatch"
            item["source_url"] = _blob_url(SPECDETECT_REPO, SPECDETECT_COMMIT, kit_path, line)
            if matches:
                _add_snippet(item, lines)
        items.append(item)
    return items


def _smelly_owner(tree: ast.Module, line: int) -> tuple[str, str | None]:
    """Innermost class and method that contain `line` (comments above a def belong to it)."""
    owner_class, owner_function = "", None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.lineno <= line + 1 <= node.end_lineno:
            owner_class = node.name
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.lineno <= line + 1 <= child.end_lineno:
                    owner_function = child.name
    return owner_class, owner_function


def build_smelly(smelly_dir: Path) -> list[dict]:
    items = []
    for path in sorted(smelly_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for number, text in enumerate(source.splitlines(), start=1):
            match = SMELLY_COMMENT.search(text)
            if not match:
                continue
            smell = match.group(1)
            owner_class, owner_function = _smelly_owner(tree, number)
            category = SMELLY_SMELLS[smell]
            item = {
                "id": f"smelly_{len(items) + 1:03d}",
                "source": "smelly_code",
                "smell": smell,
                "category_v1": category,
                "label": 1,
                "file": path.name,
                "class": owner_class,
                "function": owner_function,
                "line": number,
            }
            if category and owner_function:
                function_line = next(
                    n.lineno for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == owner_function
                    and n.lineno <= number <= n.end_lineno
                )
                measures = _v1_measures(source, function_line)
                item["v1_measures"] = measures
                item["meets_v1_threshold"] = _meets_v1(category, measures)
            items.append(item)
    return items


def _summary(pysmell: list[dict], smelly: list[dict], mlflow: list[dict], codesmile: list[dict]) -> dict:
    def by_smell(items: list[dict]) -> dict:
        counts: dict[str, Counter] = {}
        for item in items:
            counts.setdefault(item["smell"] or "(no smell in file)", Counter())[f"label_{item['label']}"] += 1
        return {smell: dict(sorted(c.items())) for smell, c in sorted(counts.items())}

    return {
        "pysmell": {
            "items": len(pysmell),
            "location": dict(Counter(item["location"] for item in pysmell)),
            "positives_by_location": dict(Counter(item["location"] for item in pysmell if item["label"] == 1)),
            "by_smell": by_smell(pysmell),
            "v1_mapped_positives_meeting_threshold": dict(Counter(
                f"{item['category_v1']}={item.get('meets_v1_threshold')}"
                for item in pysmell if item["category_v1"] and item["label"] == 1
            )),
        },
        "smelly_code": {
            "items": len(smelly),
            "by_smell": by_smell(smelly),
            "v1_mapped_meeting_threshold": dict(Counter(
                f"{item['category_v1']}={item.get('meets_v1_threshold')}"
                for item in smelly if item["category_v1"]
            )),
        },
        "mlflow": {
            "items": len(mlflow),
            "files": len({item["path"] for item in mlflow}),
            "location": dict(Counter(item["location"] for item in mlflow)),
            "by_smell": by_smell(mlflow),
        },
        "codesmile": {
            "items": len(codesmile),
            "files": len({item["path"] for item in codesmile}),
            "location": dict(Counter(item["location"] for item in codesmile)),
            "positives_by_location": dict(Counter(item["location"] for item in codesmile if item["label"] == 1)),
            "by_smell": by_smell(codesmile),
        },
    }


VALIDATED_BY = {
    "pysmell": "PySmell manual inspection (Chen et al.)",
    "specdetect4ai_mlflow": "SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus",
    "specdetect4ai_codesmile": "SpecDetect4AI re-annotation of CodeSmile, adjudicated",
}
CONFIRMED_LOCATIONS = {
    "pysmell": {"verified", "file_verified"},
    "specdetect4ai_mlflow": {"unverified"},
    "specdetect4ai_codesmile": {"verified"},
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def write_py_files(items: list[dict], out: Path) -> Counter:
    """One .py per (smell, snippet) among human-validated positives whose location was confirmed."""
    groups: dict[tuple, list[dict]] = {}
    for item in items:
        if item["label"] == 1 and item.get("snippet") and item["location"] in CONFIRMED_LOCATIONS[item["source"]]:
            key = (item["smell"], item["source"], item["path"], item["snippet_start"])
            groups.setdefault(key, []).append(item)
    shutil.rmtree(out, ignore_errors=True)
    written: Counter = Counter()
    for (smell, source, _, start), group in sorted(groups.items(), key=lambda kv: kv[1][0]["id"]):
        first = group[0]
        rule = f" ({first['rule']})" if first.get("rule") else ""
        lines = sorted({item["line"] for item in group})
        header = [
            f"# smell: {smell}{rule}",
            f"# validated by: {VALIDATED_BY[source]}",
            f"# origin: {first['source_url'].split('#')[0]}#L{first['snippet_start']}-L{first['snippet_end']}",
            f"# smelly line(s) in the original file: {', '.join(map(str, lines))}",
            "# smelly line(s) in this file: {}",
            f"# ids: {', '.join(item['id'] for item in group)}",
        ]
        if source == "pysmell":
            header.append("# note: Python 2 era source, kept as found")
        offset = len(header) + 1 - start
        header[4] = header[4].format(", ".join(str(n + offset) for n in lines))
        target = out / _slug(smell) / f"{first['id']}.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(header) + "\n" + first["snippet"] + "\n", encoding="utf-8")
        written[smell] += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "dataset" / "code_smell")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "llm_esbmc" / "code_smell_sources")
    args = parser.parse_args()

    pysmell = build_pysmell(args.cache)
    smelly = build_smelly(args.out / "smelly_code")
    mlflow = build_mlflow(args.cache)
    codesmile = build_codesmile(args.cache)
    for name, items in (("pysmell_manual", pysmell), ("mlflow_ml_smells", mlflow),
                        ("codesmile_ml_smells", codesmile)):
        with (args.out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    (args.out / "smelly_code_labels.json").write_text(
        json.dumps(smelly, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = _summary(pysmell, smelly, mlflow, codesmile)
    summary["py_files"] = dict(sorted(write_py_files(pysmell + mlflow + codesmile, args.out / "files").items()))
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
