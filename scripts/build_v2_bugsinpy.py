"""Add the staged BugsInPy candidates to dataset/bugs_reais/, tagged ``"cohort": "rotulo_automatico"``.

Only candidates whose suspect expression grounds in the buggy function are kept. The detection file
is cut from the real buggy file (the function, inside its class header for a method), so it always
matches arquivo_com_bug/. Categories stay as labels.json has them (heuristic or "unclassified"):
in V2 they are metadata, and detection is scored by location. Rerunning replaces the cohort.
"""

from __future__ import annotations

import ast
import difflib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.astutil import expression_nodes, find_function  # noqa: E402

STAGING = ROOT / "dataset" / "coleta_bugsinpy"
TARGET = ROOT / "dataset" / "bugs_reais"
COHORT = "rotulo_automatico"
FOLDERS = ("funcao_com_bug", "arquivo_com_bug", "arquivo_corrigido", "patches")


def excerpt(source: str, qualified: str) -> str | None:
    """The function as it stands in the file; a method keeps its class header so it can be found."""
    tree = ast.parse(source)
    function = find_function(tree, qualified)
    if function is None:
        return None
    lines = source.splitlines()
    first = min([function.lineno, *(d.lineno for d in function.decorator_list)])
    body = lines[first - 1:function.end_lineno]
    if "." not in qualified:
        return "\n".join(line[function.col_offset:] for line in body) + "\n"
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and function in n.body)
    # Bases can span lines and name other modules; the detection file only needs the class name.
    header = f"class {cls.name}:"
    indent = " " * 4
    return header + "\n" + "\n".join(indent + line[function.col_offset:] if line.strip() else ""
                                     for line in body) + "\n"


def build() -> Counter:
    candidates = {c["id"]: c for c in json.loads((STAGING / "bugsinpy_candidates.json").read_text(encoding="utf-8"))}
    labels = json.loads((STAGING / "labels.json").read_text(encoding="utf-8"))
    documents = {name: json.loads((TARGET / name).read_text(encoding="utf-8"))
                 for name in ("manifest.json", "ground_truths.json")}
    for document in documents.values():
        stale = {item["id"] for item in document["items"] if item.get("cohort") == COHORT}
        document["items"] = [item for item in document["items"] if item["id"] not in stale]
        for key in stale:
            for sub in FOLDERS:
                for path in (TARGET / sub).glob(f"{key}.*"):
                    path.unlink()
    curated = {item["id"] for item in documents["ground_truths.json"]["items"]}
    counts: Counter = Counter()
    manifest, truths = [], []
    for label in labels:
        key = label["id"]
        if key in curated:
            raise SystemExit(f"{key} already exists in {TARGET} outside the {COHORT} cohort")
        if not label.get("grounded"):
            counts["skipped: expression not in the buggy function"] += 1
            continue
        if label["expression"].lstrip().startswith(("def ", "async def ", "class ")):
            # The fix rewrote a nested definition: no expression in it locates the bug.
            counts["skipped: the changed statement is a whole definition"] += 1
            continue
        buggy = (STAGING / "sources" / f"{key}.buggy.py").read_text(encoding="utf-8", errors="replace")
        fixed = (STAGING / "sources" / f"{key}.fixed.py").read_text(encoding="utf-8", errors="replace")
        cut = excerpt(buggy, label["function"])
        if cut is None or not expression_nodes(find_function(ast.parse(cut), label["function"]), label["expression"]):
            counts["skipped: excerpt does not hold the expression"] += 1
            continue
        name = f"{key}.py"
        (TARGET / "funcao_com_bug" / name).write_text(cut, encoding="utf-8")
        (TARGET / "arquivo_com_bug" / name).write_text(buggy, encoding="utf-8")
        (TARGET / "arquivo_corrigido" / name).write_text(fixed, encoding="utf-8")
        candidate = candidates[key]
        source_file = candidate["source_file"]
        patch = difflib.unified_diff(buggy.splitlines(keepends=True), fixed.splitlines(keepends=True),
                                     f"a/{source_file}", f"b/{source_file}")
        (TARGET / "patches" / f"{key}.diff").write_text("".join(patch), encoding="utf-8")
        provenance = {k: candidate[k] for k in ("project", "bugsinpy_id", "repo_url", "buggy_commit",
                                               "fixed_commit", "source_file")}
        provenance["source_function"] = candidate["function"]
        item = {"id": key, "cohort": COHORT, "function": label["function"], "expression": label["expression"],
                "categories": [label["category"]], "line": label.get("line"),
                "label_sources": {"expression": label["expression_source"], "category": label["category_source"]},
                "review": label["review"], "provenance": provenance}
        manifest.append({**item, "detection_file": f"funcao_com_bug/{name}"})
        truths.append({**item, "file": name})
        counts["kept"] += 1
        counts[f"category: {label['category']}"] += 1
    documents["manifest.json"]["items"] += manifest
    documents["ground_truths.json"]["items"] += truths
    for name, document in documents.items():
        (TARGET / name).write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return counts


if __name__ == "__main__":
    for reason, count in sorted(build().items()):
        print(f"{count:4d}  {reason}")
