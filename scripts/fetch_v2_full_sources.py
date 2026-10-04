"""Fetch the complete buggy source file of each V2 case, keeping detection/ untouched.

For every manifest item, download <repo>/<commit>/<source_file> from
raw.githubusercontent.com (buggy_commit, then parent_commit, then commit_hash)
and accept it only when the target function is AST-identical to the one in
detection/, which pins the buggy version. Writes arquivo_com_bug/<id>.py and
arquivo_com_bug/fetch_report.json.
"""

from __future__ import annotations

import argparse
import ast
import json
import time
from pathlib import Path
from urllib import error, request


_DEFS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _one_function(tree: ast.Module, qualified: str) -> ast.AST | None:
    """Resolve Class.method or outer.inner; excerpts may repeat a class once per method."""
    parts = qualified.split(".")
    scope = tree.body
    for name in parts[:-1]:
        scope = [n for c in scope if isinstance(c, _DEFS) and c.name == name for n in c.body]
    found = [n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == parts[-1]]
    return found[0] if len(found) == 1 else None


def _function(source: str, qualified: str) -> ast.AST | None:
    """The labelled function, or all of them when the label lists several ("f / g")."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    found = [_one_function(tree, name.strip()) for name in qualified.split(" / ")]
    if None in found:
        return None
    return found[0] if len(found) == 1 else ast.Module(body=found, type_ignores=[])


def _without_docstrings(node: ast.AST) -> str:
    """Docstrings and annotations carry no behaviour and dataset extraction sometimes dropped them."""
    import copy
    node = copy.deepcopy(node)
    for child in ast.walk(node):
        if isinstance(child, ast.arg):
            child.annotation = None
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            child.returns = None
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


def _download(url: str, attempts: int = 3) -> str | None:
    for attempt in range(attempts):
        try:
            with request.urlopen(url, timeout=30) as response:  # noqa: S310 -- fixed https host
                return response.read().decode("utf-8")
        except error.HTTPError as exc:
            if exc.code == 404:
                return None
        except (error.URLError, TimeoutError):
            pass
        except UnicodeDecodeError:
            return None
        time.sleep(2 * (attempt + 1))
    return None


def _parent(repo_url: str, commit: str) -> str | None:
    """First parent via the public GitHub API: some manifests record the fix commit as buggy."""
    owner_repo = repo_url.rstrip("/").removeprefix("https://github.com/").removesuffix(".git")
    url = f"https://api.github.com/repos/{owner_repo}/commits/{commit}"
    try:
        with request.urlopen(url, timeout=30) as response:  # noqa: S310 -- fixed https host
            parents = json.loads(response.read().decode("utf-8")).get("parents") or []
    except (error.URLError, TimeoutError, ValueError):
        return None
    return parents[0]["sha"] if parents else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="dataset/bugs_reais")
    parser.add_argument("--only-unmatched", action="store_true",
                        help="keep existing matches; retry the rest, adding each commit's parent")
    args = parser.parse_args()
    root = Path(args.dataset)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    out = root / "arquivo_com_bug"
    out.mkdir(exist_ok=True)
    previous_path = out / "fetch_report.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    report = {}
    # The BugsInPy cohort gets its complete files from build_v2_bugsinpy.py.
    curated = [item for item in manifest["items"] if "cohort" not in item]
    for item in curated:
        case_id = str(item["id"])
        if args.only_unmatched and str(previous.get(case_id, "")).startswith("matched"):
            report[case_id] = previous[case_id]
            continue
        prov = item.get("provenance", {})
        detection = (root / item["detection_file"]).read_text(encoding="utf-8")
        expected = _function(detection, str(item["function"]))
        commits = [prov[key] for key in ("buggy_commit", "parent_commit", "commit_hash") if prov.get(key)]
        if args.only_unmatched:
            commits += [parent for parent in (_parent(prov["repo_url"], c) for c in commits[:1]) if parent]
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
    # Starts from the existing manifest_full, whose harness_file paths are newer than manifest.json's.
    full_path = root / "manifest_full.json"
    full = json.loads(full_path.read_text(encoding="utf-8")) if full_path.exists() else dict(manifest)
    existing = {str(item["id"]): item for item in full.get("items", [])}
    full["items"] = []
    for item in curated:
        case_id = str(item["id"])
        base = existing.get(case_id, item)
        verified = report[case_id].startswith("matched")
        full["items"].append({**base, "detection_file": f"arquivo_com_bug/{case_id}.py" if verified else item["detection_file"]})
    full_path.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    matched = sum(value.startswith("matched") for value in report.values())
    print(f"matched {matched}/{len(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
