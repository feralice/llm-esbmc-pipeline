from pathlib import Path

from research_pipeline.scan.callgraph import build_callgraph, python_files


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _edges(graph) -> set[tuple[str, str]]:
    return {(s.caller, s.callee) for s in graph.calls if s.callee}


def test_cross_module_from_import_and_module_attribute(tmp_path: Path) -> None:
    root = _repo(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/util.py": "def ratio(a, b):\n    return a / b\n",
        "pkg/app.py": "from pkg.util import ratio\nimport pkg.util as u\nfrom . import util\n\n"
                      "def run(x):\n    return ratio(x, 2) + u.ratio(x, 3) + util.ratio(1, x)\n",
    })
    graph = build_callgraph(root)
    sites = graph.callers("pkg.util:ratio")
    assert [(s.caller, s.line) for s in sites] == [("pkg.app:run", 6)] * 3
    assert [s.caller for s in graph.callees("pkg.app:run")] == ["pkg.app:run"] * 3


def test_relative_import_of_a_name_from_a_sibling(tmp_path: Path) -> None:
    root = _repo(tmp_path, {
        "pkg/__init__.py": "from .core import parse\n",
        "pkg/core.py": "def parse(s):\n    return int(s)\n",
        "main.py": "from pkg import parse\n\ndef go():\n    return parse('1')\n",
    })
    assert ("main:go", "pkg.core:parse") in _edges(build_callgraph(root))


def test_self_method_and_inherited_method_from_another_module(tmp_path: Path) -> None:
    root = _repo(tmp_path, {
        "base.py": "class Base:\n    def size(self):\n        return 1\n",
        "box.py": "from base import Base\n\nclass Box(Base):\n"
                  "    def __init__(self, n):\n        self.n = n\n"
                  "    def half(this):\n        return this.size() / this.total()\n"
                  "    def total(self):\n        return self.n\n"
                  "def make():\n    return Box(3).half()\n",
    })
    edges = _edges(build_callgraph(root))
    assert ("box:Box.half", "base:Base.size") in edges
    assert ("box:Box.half", "box:Box.total") in edges
    assert ("box:make", "box:Box.__init__") in edges


def test_super_call_resolves_to_the_base_method(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"m.py": "class A:\n    def f(self):\n        return 1\n"
                                    "class B(A):\n    def f(self):\n        return super().f() + 1\n"})
    assert ("m:B.f", "m:A.f") in _edges(build_callgraph(root))


def test_nested_function_is_indexed_but_not_reachable_by_the_engine(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"m.py": "def outer(x):\n    def inner(y):\n        return 1 / y\n"
                                    "    return inner(x)\n"})
    graph = build_callgraph(root)
    inner = graph.functions["m:outer.inner"]
    assert inner.nested and not inner.verifiable
    assert graph.functions["m:outer"].verifiable
    assert [s.caller for s in graph.callers("m:outer.inner")] == ["m:outer"]
    assert not graph.callees("m:outer.inner")


def test_external_and_shadowed_calls_get_no_callee(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"m.py": "import os\n\ndef helper():\n    return 0\n\n"
                                    "def f(helper, path):\n    os.path.join(path)\n    len(path)\n"
                                    "    return helper()\n"})
    graph = build_callgraph(root)
    assert not graph.callers("m:helper")
    assert {s.expression for s in graph.external_calls("m:f")} == {"os.path.join", "len", "helper"}


def test_syntax_error_file_is_skipped_and_reported(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"good.py": "def f():\n    return 1\n", "bad.py": "def f(:\n"})
    graph = build_callgraph(root)
    assert [s["file"] for s in graph.skipped] == ["bad.py"]
    assert "SyntaxError" in graph.skipped[0]["error"]
    assert "good:f" in graph.functions and graph.stats()["skipped_files"] == 1


def test_skipped_directories_and_tests_unless_asked(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": "", ".venv/x.py": "", "build/y.py": "", "tests/test_a.py": "",
                            "pkg/test_b.py": "", "conftest.py": ""})
    assert [p.name for p in python_files(root)] == ["a.py"]
    assert sorted(p.name for p in python_files(root, include_tests=True)) == [
        "a.py", "conftest.py", "test_a.py", "test_b.py"]


def test_redefined_function_is_ambiguous_and_not_verifiable(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"m.py": "def f():\n    return 1\ndef f():\n    return 2\n"
                                    "if True:\n    def g():\n        return 3\n"})
    graph = build_callgraph(root)
    assert graph.functions["m:f"].ambiguous and not graph.functions["m:f"].verifiable
    assert not graph.functions["m:g"].verifiable


def test_staticmethod_first_parameter_is_not_a_receiver(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"m.py": "class C:\n    @staticmethod\n    def s(obj):\n        return obj.g()\n"
                                    "    def g(self):\n        return 1\n"})
    assert not build_callgraph(root).callers("m:C.g")


def test_src_layout_import_resolves_by_unique_suffix(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"src/lib/__init__.py": "", "src/lib/core.py": "def f(x):\n    return x\n",
                            "src/lib/use.py": "from lib.core import f\n\ndef g():\n    return f(1)\n"})
    assert ("src.lib.use:g", "src.lib.core:f") in _edges(build_callgraph(root))


def test_a_root_that_is_a_package_resolves_its_absolute_self_imports(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"lib/__init__.py": "", "lib/core.py": "def f(x):\n    return x\n",
                            "lib/use.py": "from lib.core import f\n\ndef g():\n    return f(1)\n"})
    assert ("lib.use:g", "lib.core:f") in _edges(build_callgraph(root / "lib"))
