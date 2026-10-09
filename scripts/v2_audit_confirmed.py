"""Audit of CONFIRMED verdicts under a stricter criterion (second opinion of 2026-10-09).

The pipeline's CONFIRMED pairs an ESBMC violation of an exception type with a CPython replay that
raises that type at the hypothesis line, possibly on another input: ESBMC reports Python exceptions
as a global property (line 0) and, in 8.5.0, prints no counterexample values for these programs.

This audit proves the location formally. On a copy of the verified program only, the statement
holding the hypothesis is wrapped in ``try: ... except <Exc>: __ESBMC_assert(False, "AUDIT_TARGET")``;
an ESBMC failure of AUDIT_TARGET shows the exception is raised at that statement. It also lists the
stubs the statement uses, whose behaviour has to be checked by hand against the real library.

  python scripts/v2_audit_confirmed.py --out artifacts/v2/audit-2026-10-09
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.astutil import expression_nodes, find_function  # noqa: E402

_TARGET = re.compile(r"FAILED\s+\[[^\]]+\]\s+line\s+\d+\s+AUDIT_TARGET")


def _target_nodes(target, expression: str) -> list:
    """The hypothesis as written, or with slicing's stub renames (``re.findall`` -> ``_esbmc_re_findall``)."""
    if target is None:
        return []
    return (expression_nodes(target, expression)
            or expression_nodes(target, re.sub(r"\b(\w+)\.(\w+)\(", r"_esbmc_\1_\2(", expression)))


def wrap_target(source: str, function: str, expression: str, exception: str) -> str | None:
    """``source`` with the statement holding ``expression`` inside ``function`` wrapped so that
    ``exception`` raised there fails an ESBMC assertion; None when it cannot be placed."""
    tree = ast.parse(source)
    target = find_function(tree, function)
    nodes = _target_nodes(target, expression)
    if not nodes:
        return None
    line = nodes[0].lineno
    covering = [n for n in ast.walk(target) if isinstance(n, ast.stmt) and n is not target
                and n.lineno <= line <= (n.end_lineno or n.lineno)]
    statement = min(covering, key=lambda n: (n.end_lineno or n.lineno) - n.lineno)
    lines = source.splitlines()
    indent = " " * statement.col_offset
    body = ["    " + text for text in lines[statement.lineno - 1:statement.end_lineno]]
    wrapped = ([f"{indent}try:"] + body
               + [f"{indent}except {exception}:", f'{indent}    __ESBMC_assert(False, "AUDIT_TARGET")',
                  f"{indent}    raise"])
    audited = "\n".join(lines[:statement.lineno - 1] + wrapped + lines[statement.end_lineno:]) + "\n"
    try:
        ast.parse(audited)
    except SyntaxError:
        return None
    return audited


def stubs_on_line(source: str, function: str, expression: str) -> list[str]:
    nodes = _target_nodes(find_function(ast.parse(source), function), expression)
    names = {n.id for node in nodes for n in ast.walk(node) if isinstance(n, ast.Name)}
    defined = {n.name for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    return sorted(n for n in names if n.startswith("_esbmc_") or (n in defined and n != function.split(".")[-1]))


def cases() -> list[dict]:
    a2 = "artifacts/v2/"
    level1 = json.loads(Path(a2 + "full-2026-10-05-regrounded/v2_verify_report.json").read_text())["results"]
    rows = [{"bug": Path(r["hypothesis"]["file"]).stem, "level": "nivel 1", "program": r["program_path"],
             "function": r["hypothesis"]["function"], "expression": r["hypothesis"]["suspect_expression"],
             "exception": r["replay"]["exception_type"]}
            for r in level1 if r["verdict"] == "CONFIRMED"]
    agent = {a["hypothesis"]["hypothesis_id"]: a
             for a in json.loads(Path(a2 + "agent-2026-10-05-sonnet/agent_results.json").read_text())}
    for r in json.loads(Path(a2 + "agent-2026-10-05-sonnet-reverify.json").read_text()):
        if r["verdict"] == "CONFIRMED":
            a = agent[r["id"]]
            rows.append({"bug": Path(a["hypothesis"]["file"]).stem, "level": "agente", "program": a["harness_path"],
                         "function": a["hypothesis"]["function"], "expression": a["hypothesis"]["suspect_expression"],
                         "exception": (r.get("replay") or {}).get("exception_type", "")})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--esbmc", default="/usr/local/bin/esbmc")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--only", default="", help="comma-separated bug ids")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = []
    wanted = set(filter(None, args.only.split(",")))
    for case in [c for c in cases() if not wanted or c["bug"] in wanted]:
        source = Path(case["program"]).read_text(encoding="utf-8")
        function = case["function"] if find_function(ast.parse(source), case["function"]) else case["function"].split(".")[-1]
        row = {**case, "stubs_on_line": stubs_on_line(source, function, case["expression"])}
        audited = None if case["exception"] == "AssertionError" else wrap_target(
            source, function, case["expression"], case["exception"])
        if case["exception"] == "AssertionError":
            row["located"] = "assert statement: ESBMC reports its own line"
        elif audited is None:
            row["located"] = "could not wrap the statement"
        else:
            path = out / f"{case['bug']}_{Path(case['program']).stem}_audit.py"
            path.write_text(audited, encoding="utf-8")
            try:
                done = subprocess.run([args.esbmc, str(path), "--unwind", "5", "--multi-property"],
                                      capture_output=True, text=True, timeout=args.timeout, check=False)
                output = done.stdout + done.stderr
                row["located"] = "yes" if _TARGET.search(output) else "no"
                row["esbmc_tail"] = [ln for ln in output.splitlines() if "AUDIT_TARGET" in ln or ln.startswith(
                    ("VERIFICATION", "ERROR"))][-3:]
            except subprocess.TimeoutExpired:
                row["located"] = "timeout"
        report.append(row)
        print(f"{row['bug']:14} {row['level']:8} {row['exception']:18} located={row['located']:8} "
              f"stubs={row['stubs_on_line']}", flush=True)
    (out / ("audit.json" if not wanted else "audit_" + "_".join(sorted(wanted)) + ".json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
