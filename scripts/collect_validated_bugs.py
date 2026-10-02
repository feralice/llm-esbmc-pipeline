"""Collect maintainer-validated Python bugs into a staging area for the V2 dataset.

A bug is accepted only when its fix is in the project's official history and a test proves it:
- BugsInPy: every bug has a buggy commit, a fixed commit and a test that fails before the fix;
- GitHub pull requests: the PR must be merged and must add or change a test file.

Each candidate keeps full provenance and must change exactly one function in one non-test file.
Candidates land in dataset/coleta_bugsinpy/ (never in dataset/bugs_reais/); moving them into the
dataset goes through the existing audit gates.

Usage:
  python scripts/collect_validated_bugs.py bugsinpy [--limit N]
  python scripts/collect_validated_bugs.py prs dataset/coleta_bugsinpy/pr_sources.json
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "dataset" / "coleta_bugsinpy"
BUGSINPY_ZIP = "https://codeload.github.com/soarsmu/BugsInPy/zip/refs/heads/master"
_TEST_PATH = re.compile(r"(^|/)(tests?|testing)(/|_)|(^|/)test_[^/]*\.py$|_test\.py$|conftest\.py$")


@dataclass
class Hunk:
    old_start: int
    old_len: int
    removed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    changed_old_lines: list[int] = field(default_factory=list)


def parse_unified_diff(patch: str) -> dict[str, list[Hunk]]:
    """Hunks per file, with the old-file line numbers each change touches."""
    files: dict[str, list[Hunk]] = {}
    current: list[Hunk] | None = None
    hunk: Hunk | None = None
    old_line = 0
    for line in patch.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            path = path[2:] if path.startswith("b/") else path
            current = files.setdefault(path, [])
            continue
        if line.startswith(("--- ", "diff --git", "index ", "new file", "deleted file")):
            continue
        header = re.match(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", line)
        if header and current is not None:
            hunk = Hunk(int(header.group(1)), int(header.group(2) or 1))
            current.append(hunk)
            old_line = hunk.old_start
            continue
        if hunk is None:
            continue
        if line.startswith("-"):
            hunk.removed.append(line[1:])
            hunk.changed_old_lines.append(old_line)
            old_line += 1
        elif line.startswith("+"):
            hunk.added.append(line[1:])
            # A pure insertion sits after the previous old line.
            if not hunk.changed_old_lines or hunk.changed_old_lines[-1] != max(old_line - 1, 1):
                hunk.changed_old_lines.append(max(old_line - 1, 1))
        elif not line.startswith("\\"):
            old_line += 1
    return files


def enclosing_function(source: str, lines: list[int]) -> str | None:
    """Innermost top-level function or class method containing every line, qualified as Class.method."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    candidates = []
    for node in tree.body:
        scopes = [(node, "")] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else []
        if isinstance(node, ast.ClassDef):
            scopes = [(m, f"{node.name}.") for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for scope, prefix in scopes:
            start = min([scope.lineno, *(d.lineno for d in scope.decorator_list)])
            if all(start <= line <= scope.end_lineno for line in lines):
                candidates.append(prefix + scope.name)
    return candidates[0] if len(candidates) == 1 else None


def select_single_function(hunks: dict[str, list[Hunk]], sources: dict[str, str]):
    """(file, function, removed lines) when the fix touches one function of one source file; else a reason."""
    source_files = [path for path in hunks if path.endswith(".py") and not _TEST_PATH.search(path)]
    if len(source_files) != 1:
        return f"fix touches {len(source_files)} non-test Python files"
    path = source_files[0]
    lines = [line for h in hunks[path] for line in h.changed_old_lines]
    function = enclosing_function(sources.get(path, ""), lines)
    if function is None:
        return "changed lines are not inside exactly one top-level function or method"
    removed = [line.strip() for h in hunks[path] for line in h.removed if line.strip()]
    return path, function, removed


def _get(url: str, *, binary: bool = False, retries: int = 2):
    for attempt in range(retries + 1):
        try:
            with request.urlopen(url, timeout=60) as response:  # noqa: S310 -- fixed github hosts
                data = response.read()
                return data if binary else data.decode("utf-8")
        except (error.URLError, TimeoutError, UnicodeDecodeError):
            if attempt == retries:
                return None
            time.sleep(2)
    return None


def _raw(repo_url: str, commit: str, path: str) -> str | None:
    owner_repo = repo_url.rstrip("/").removeprefix("https://github.com/").removesuffix(".git")
    return _get(f"https://raw.githubusercontent.com/{owner_repo}/{commit}/{path}")


def _info(text: str) -> dict[str, str]:
    return {k.strip(): v.strip().strip('"') for k, v in re.findall(r"^([\w ]+?)\s*=\s*(.*)$", text, re.M)}


def _existing_bugsinpy() -> set[tuple[str, str]]:
    items = json.loads((ROOT / "dataset/bugs_reais/ground_truths.json").read_text(encoding="utf-8"))["items"]
    return {(i["provenance"]["project"], str(i["provenance"].get("bugsinpy_id"))) for i in items
            if i.get("provenance", {}).get("bugsinpy_id")}


def _save(candidate: dict, buggy: str, fixed: str | None) -> None:
    sources = STAGING / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / f"{candidate['id']}.buggy.py").write_text(buggy, encoding="utf-8")
    if fixed is not None:
        (sources / f"{candidate['id']}.fixed.py").write_text(fixed, encoding="utf-8")


def _write(name: str, accepted: list[dict], rejected: list[dict]) -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    (STAGING / f"{name}_candidates.json").write_text(json.dumps(accepted, indent=2, ensure_ascii=False), encoding="utf-8")
    (STAGING / f"{name}_rejected.json").write_text(json.dumps(rejected, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{name}: {len(accepted)} aceitos, {len(rejected)} recusados -> {STAGING}")


def collect_bugsinpy(limit: int = 0) -> None:
    archive = _get(BUGSINPY_ZIP, binary=True)
    if archive is None:
        sys.exit("could not download BugsInPy")
    zf = zipfile.ZipFile(io.BytesIO(archive))
    names = zf.namelist()
    existing = _existing_bugsinpy()
    accepted, rejected = [], []
    bug_dirs = sorted({n.rsplit("/", 1)[0] for n in names if re.search(r"/projects/[^/]+/bugs/\d+/bug\.info$", n)},
                      key=lambda d: (d.split("/projects/")[1].split("/")[0], int(d.rsplit("/", 1)[1])))
    for bug_dir in bug_dirs:
        project, bug_id = bug_dir.split("/projects/")[1].split("/bugs/")
        record = {"source": "bugsinpy", "project": project, "bugsinpy_id": bug_id}
        if (project, bug_id) in existing:
            continue
        project_info = _info(zf.read(bug_dir.split("/bugs/")[0] + "/project.info").decode("utf-8", "replace"))
        info = _info(zf.read(bug_dir + "/bug.info").decode("utf-8", "replace"))
        patch_name = bug_dir + "/bug_patch.txt"
        if patch_name not in names:
            rejected.append({**record, "reason": "no bug_patch.txt"})
            continue
        hunks = parse_unified_diff(zf.read(patch_name).decode("utf-8", "replace"))
        source_files = [p for p in hunks if p.endswith(".py") and not _TEST_PATH.search(p)]
        if len(source_files) != 1:
            rejected.append({**record, "reason": f"fix touches {len(source_files)} non-test Python files"})
            continue
        repo, buggy_commit, fixed_commit = project_info.get("github_url", ""), info.get("buggy_commit_id", ""), info.get("fixed_commit_id", "")
        buggy = _raw(repo, buggy_commit, source_files[0])
        if buggy is None:
            rejected.append({**record, "reason": "buggy source not downloadable"})
            continue
        choice = select_single_function(hunks, {source_files[0]: buggy})
        if isinstance(choice, str):
            rejected.append({**record, "reason": choice})
            continue
        path, function, removed = choice
        candidate = {
            "id": f"bip_{project.replace('-', '_')}_{bug_id}", **record, "repo_url": repo,
            "buggy_commit": buggy_commit, "fixed_commit": fixed_commit, "source_file": path, "function": function,
            "removed_lines": removed, "validation": {"fix_in_official_history": True,
                                                     "failing_test": info.get("test_file", "")},
        }
        _save(candidate, buggy, _raw(repo, fixed_commit, path))
        accepted.append(candidate)
        print(f"  + {candidate['id']}: {path}::{function}", flush=True)
        if limit and len(accepted) >= limit:
            break
    _write("bugsinpy", accepted, rejected)


def collect_prs(sources_file: Path) -> None:
    entries = json.loads(sources_file.read_text(encoding="utf-8"))
    accepted, rejected = [], []
    for entry in entries:
        match = re.match(r"https://github.com/([^/]+/[^/]+)/pull/(\d+)", entry["url"])
        record = {"source": "pull_request", "url": entry["url"], "note": entry.get("note", "")}
        if not match:
            rejected.append({**record, "reason": "not a GitHub pull request URL"})
            continue
        api = f"https://api.github.com/repos/{match.group(1)}/pulls/{match.group(2)}"
        pr, files = _get(api), _get(api + "/files")
        if pr is None or files is None:
            rejected.append({**record, "reason": "GitHub API unavailable (rate limit?)"})
            continue
        pr, files = json.loads(pr), json.loads(files)
        if not pr.get("merged"):
            rejected.append({**record, "reason": "pull request not merged"})
            continue
        if not any(_TEST_PATH.search(f["filename"]) for f in files):
            rejected.append({**record, "reason": "pull request changes no test file"})
            continue
        patch = "".join(f"+++ b/{f['filename']}\n{f.get('patch', '')}\n" for f in files if f.get("patch"))
        hunks = parse_unified_diff(patch)
        source_files = [p for p in hunks if p.endswith(".py") and not _TEST_PATH.search(p)]
        repo = f"https://github.com/{match.group(1)}"
        base, merged = pr["base"]["sha"], pr["merge_commit_sha"]
        buggy = _raw(repo, base, source_files[0]) if len(source_files) == 1 else None
        choice = select_single_function(hunks, {source_files[0]: buggy} if buggy else {})
        if isinstance(choice, str):
            rejected.append({**record, "reason": choice})
            continue
        path, function, removed = choice
        candidate = {
            "id": f"pr_{match.group(1).replace('/', '_').replace('-', '_')}_{match.group(2)}", **record,
            "repo_url": repo, "buggy_commit": base, "fixed_commit": merged, "source_file": path,
            "function": function, "removed_lines": removed,
            "validation": {"merged_at": pr.get("merged_at"),
                           "tests_changed": [f["filename"] for f in files if _TEST_PATH.search(f["filename"])]},
        }
        _save(candidate, buggy, _raw(repo, merged, path))
        accepted.append(candidate)
    _write("prs", accepted, rejected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="source", required=True)
    bip = sub.add_parser("bugsinpy")
    bip.add_argument("--limit", type=int, default=0)
    prs = sub.add_parser("prs")
    prs.add_argument("sources_file", type=Path)
    args = parser.parse_args()
    if args.source == "bugsinpy":
        collect_bugsinpy(args.limit)
    else:
        collect_prs(args.sources_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
