"""Fetch the complete buggy source file of each V2 case, keeping detection/ untouched.

For every manifest item, download <repo>/<commit>/<source_file> from
raw.githubusercontent.com (buggy_commit, then parent_commit, then commit_hash)
and accept it only when the target function is AST-identical to the one in
detection/, which pins the buggy version. Writes detection_full/<id>.py and
detection_full/fetch_report.json.
"""

from __future__ import annotations

import argparse
import ast
import json
import time
from pathlib import Path
from urllib import error, request


def _function(source: str, qualified: str) -> ast.AST | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    parts = qualified.split(".")
    scope = tree.body
    for name in parts[:-1]:
        classes = [n for n in scope if isinstance(n, ast.ClassDef) and n.name == name]
        if len(classes) != 1:
            return None
        scope = classes[0].body
    found = [n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == parts[-1]]
    return found[0] if len(found) == 1 else None


def _without_docstrings(node: ast.AST) -> str:
    """Docstrings carry no behaviour and dataset extraction sometimes dropped them."""
    import copy
    node = copy.deepcopy(node)
    for child in ast.walk(node):
        body = getattr(child, "body", None)
        if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)):
            child.body = body[1:] or [ast.Pass()]
    return ast.dump(node)


def _same_function(a: ast.AST | None, b: ast.AST | None) -> bool:
    return a is not None and b is not None and _without_docstrings(a) == _without_docstrings(b)


def _raw_url(repo_url: str, commit: str, path: str) -> str:
    owner_repo = repo_url.rstrip("/").removeprefix("https://github.com/").removesuffix(".git")
    return f"https://raw.githubusercontent.com/{owner_repo}/{commit}/{path}"


def _download(url: str) -> str | None:
    try:
        with request.urlopen(url, timeout=30) as response:  # noqa: S310 -- fixed https host
            return response.read().decode("utf-8")
    except (error.URLError, TimeoutError, UnicodeDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="dataset/v2_real_world")
    args = parser.parse_args()
    root = Path(args.dataset)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    out = root / "detection_full"
    out.mkdir(exist_ok=True)
    report = {}
    for item in manifest["items"]:
        case_id = str(item["id"])
        prov = item.get("provenance", {})
        detection = (root / item["detection_file"]).read_text(encoding="utf-8")
        expected = _function(detection, str(item["function"]))
        commits = [prov[key] for key in ("buggy_commit", "parent_commit", "commit_hash") if prov.get(key)]
        status = "no_commit" if not commits else "fetch_failed"
        for commit in dict.fromkeys(commits):
            source = _download(_raw_url(prov["repo_url"], commit, prov["source_file"]))
            time.sleep(0.2)
            if source is None:
                continue
            if _same_function(_function(source, str(item["function"])), expected):
                (out / f"{case_id}.py").write_text(source, encoding="utf-8")
                status = f"matched@{commit[:10]}"
                break
            status = "function_differs"
        report[case_id] = status
        print(f"{case_id:14s} {status}")
    (out / "fetch_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Same cases and labels; only detection_file points at the complete buggy file when verified.
    full = dict(manifest)
    full["items"] = [
        {**item, "detection_file": f"detection_full/{item['id']}.py"}
        if report[str(item["id"])].startswith("matched") else item
        for item in manifest["items"]
    ]
    (root / "manifest_full.json").write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    matched = sum(value.startswith("matched") for value in report.values())
    print(f"matched {matched}/{len(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
