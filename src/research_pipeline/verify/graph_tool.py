"""Call-graph queries for the harness agent (LocAgent, ACL 2025; CKGFuzzer, ICSE 2025).

``write_graph`` stores the graph of original.py as graph.json in the case folder and copies this file there
as graph.py, which the agent runs with only the standard library:

    python3 graph.py callers NAME | callees NAME | class NAME | where NAME
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def write_graph(case_dir: Path, original: str) -> None:
    import ast

    from research_pipeline.scan.callgraph import build_source_callgraph
    from research_pipeline.scan.context import caller_context

    lines = original.splitlines()
    try:
        graph = build_source_callgraph(original, "original.py")
        tree = ast.parse(original)
    except (SyntaxError, ValueError):
        graph, tree = None, None
    functions = [] if graph is None else [
        {"name": f.qualname, "lines": [f.start_line, f.end_line],
         "source": "\n".join(lines[f.start_line - 1:f.end_line]),
         "callers": caller_context(graph, key, rename=False),
         "callees": sorted({graph.functions[s.callee].qualname for s in graph.callees(key)})}
        for key, f in graph.functions.items()]
    classes = {} if tree is None else {
        node.name: ast.get_source_segment(original, node) or ""
        for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    (Path(case_dir) / "graph.json").write_text(json.dumps({"functions": functions, "classes": classes}),
                                               encoding="utf-8")
    shutil.copy(__file__, Path(case_dir) / "graph.py")


def _matches(functions: list[dict], name: str) -> list[dict]:
    exact = [f for f in functions if f["name"] == name]
    return exact or [f for f in functions if f["name"].rsplit(".", 1)[-1] == name]


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("callers", "callees", "class", "where"):
        print(__doc__)
        return 0
    command, name = argv
    data = json.loads((Path(__file__).with_name("graph.json")).read_text(encoding="utf-8"))
    if command == "class":
        print(data["classes"].get(name) or f"class {name} not found in original.py")
        return 0
    found = _matches(data["functions"], name)
    if not found:
        print(f"{name} not found in original.py")
    elif len(found) > 1 and command != "where":
        print(f"{name} is ambiguous; ask again with one of: " + ", ".join(f["name"] for f in found))
    else:
        for f in found:
            if command == "where":
                print(f"{f['name']}: lines {f['lines'][0]}-{f['lines'][1]}")
            elif command == "callers":
                print(f["callers"])
            else:
                print(", ".join(f["callees"]) or f"{f['name']} calls no function of original.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
