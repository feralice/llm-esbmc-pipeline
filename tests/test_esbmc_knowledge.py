import subprocess
from pathlib import Path

from research_pipeline.verify.esbmc_knowledge import (
    build_index,
    esbmc_root_of,
    load_index,
    lookup,
)

README = """# ESBMC-Python

## Features Supported by ESBMC-Python

Classes, lists and dictionaries.

### Type Annotations

Add a type annotation to every parameter whose type ESBMC cannot infer.

### Limitations

Async functions are not supported. The str % operator needs constant arguments.
"""


def _checkout(root: Path) -> Path:
    (root / "src/python-frontend").mkdir(parents=True)
    (root / "src/python-frontend/README.md").write_text(README, encoding="utf-8")
    for name, kind, code in [("annot_ok", "CORE", "def f(x: int) -> int:\n    return x\n"),
                             ("known", "KNOWNBUG", "async def g():\n    pass\n"),
                             ("percent", "THOROUGH", "s = '%s' % 'a'\n"),
                             ("dict_get", "CORE", "d = {}\nv = d.get('a')\n")]:
        folder = root / "regression/python" / name
        folder.mkdir(parents=True)
        (folder / "main.py").write_text(code, encoding="utf-8")
        (folder / "test.desc").write_text(f"{kind}\nmain.py\n--unwind 1\n^VERIFICATION SUCCESSFUL$\n",
                                          encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                    "--allow-empty", "-m", "a"], check=True)
    return root


def test_build_index_keeps_core_tests_and_drops_knownbug(tmp_path):
    index = build_index(_checkout(tmp_path / "esbmc"))
    names = {s.title for s in index.tests}
    assert names == {"annot_ok", "percent", "dict_get"}
    assert {"Type Annotations", "Limitations"} <= {s.title for s in index.sections}
    assert len(index.commit) == 40


def test_lookup_ranks_by_message_words(tmp_path):
    index = build_index(_checkout(tmp_path / "esbmc"))
    text = lookup(index, "Could not resolve type of receiver. Add a type annotation to the function parameter",
                  "def f(x):\n    return x.copy()\n")
    assert text.startswith("### README: Type Annotations")


def test_lookup_matches_constructs_of_the_code(tmp_path):
    index = build_index(_checkout(tmp_path / "esbmc"))
    text = lookup(index, "unsupported: non-constant argument", "msg = '%s' % name\n")
    assert "percent" in text


def test_lookup_caps_snippets(tmp_path):
    index = build_index(_checkout(tmp_path / "esbmc"))
    text = lookup(index, "type annotation async str dict get constant", "d.get(k)\n")
    assert text.count("### README:") <= 2
    assert text.count("### regression/python/") <= 3


def test_load_index_rebuilds_on_new_commit(tmp_path):
    root = _checkout(tmp_path / "esbmc")
    first = load_index(root, tmp_path / "cache")
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                    "--allow-empty", "-m", "b"], check=True)
    second = load_index(root, tmp_path / "cache")
    assert first.commit != second.commit
    assert (tmp_path / "cache" / f"{second.commit}.json").exists()


def test_missing_checkout_gives_empty_index(tmp_path):
    index = build_index(tmp_path / "nothing")
    assert index.sections == [] and index.tests == []
    assert lookup(index, "anything", "x = 1\n") == ""


def test_esbmc_root_of_walks_up_from_the_binary(tmp_path):
    root = _checkout(tmp_path / "esbmc")
    binary = root / "build/src/esbmc/esbmc"
    binary.parent.mkdir(parents=True)
    binary.write_text("", encoding="utf-8")
    assert esbmc_root_of([str(binary), "--no-pointer-check"]) == root
    assert esbmc_root_of(["/nonexistent/esbmc"]) is None
