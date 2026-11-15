"""Gabarito por função derivado do patch, sem LLM: quais funções o pull request de correção modificou.

Para cada caso do manifesto, lê o patch, localiza as linhas alteradas no arquivo com bug e devolve a função mais
interna que contém cada alteração. Não substitui o manifesto: escreve um arquivo à parte para a autora decidir
qual regra de acerto vale (função rotulada, ou qualquer função tocada pelo patch).

Uso: python scripts/gabarito_funcoes.py [--dataset dataset/disciplina_pgene601] [--out gabarito_funcoes.json]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@")


def changed_old_lines(diff: str, source_file: str) -> list[int]:
    """Old-side lines the patch removes or inserts next to, only for the file ``source_file`` (suffix match)."""
    lines, in_target, old, after_removal = [], False, 0, False
    for raw in diff.splitlines():
        if raw.startswith("--- "):
            in_target = raw[4:].strip().removeprefix("a/").endswith(source_file) or source_file.endswith(
                raw[4:].strip().removeprefix("a/"))
            continue
        if raw.startswith("+++ ") or not in_target:
            continue
        hunk = _HUNK.match(raw)
        if hunk:
            old, after_removal = int(hunk.group(1)), False
        elif raw.startswith("-"):
            lines.append(old)
            old, after_removal = old + 1, True
        elif raw.startswith("+"):
            if not after_removal:
                lines.append(old)
        elif raw.startswith(" "):
            old, after_removal = old + 1, False
    return lines


def function_spans(source: str) -> list[tuple[str, int, int]]:
    """(qualified name, first line, last line) of every function and method."""
    spans: list[tuple[str, int, int]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                if not isinstance(child, ast.ClassDef):
                    spans.append((name, child.lineno, child.end_lineno or child.lineno))
                walk(child, name + ".")
            else:
                walk(child, prefix)

    walk(ast.parse(source), "")
    return spans


def touched_functions(source: str, lines: list[int]) -> list[str]:
    spans = function_spans(source)
    found: list[str] = []
    for line in lines:
        inside = [s for s in spans if s[1] <= line <= s[2]]
        name = min(inside, key=lambda s: s[2] - s[1])[0] if inside else "<módulo>"
        if name not in found:
            found.append(name)
    return found


def build(dataset: Path) -> list[dict]:
    items = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))["items"]
    rows = []
    for item in items:
        case, labeled = item["id"], item["function"]
        source = (dataset / "arquivo_com_bug" / f"{case}.py").read_text(encoding="utf-8", errors="replace")
        diff = (dataset / "patches" / f"{case}.diff").read_text(encoding="utf-8", errors="replace")
        touched = touched_functions(source, changed_old_lines(diff, item["provenance"]["source_file"]))
        labeled_simple = [part.strip() for part in re.split(r"[/,]", labeled)]
        rows.append({
            "id": case, "rotulada": labeled, "tocadas_pelo_patch": touched,
            "rotulada_foi_tocada": any(t == n or t.endswith("." + n.split(".")[-1]) for t in touched
                                       for n in labeled_simple),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("dataset/disciplina_pgene601"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    rows = build(args.dataset)
    out = args.out or args.dataset / "gabarito_funcoes.json"
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    untouched = [r["id"] for r in rows if not r["rotulada_foi_tocada"]]
    wide = [r["id"] for r in rows if len(r["tocadas_pelo_patch"]) > 3]
    print(f"{len(rows)} casos; função rotulada não tocada pelo patch: {len(untouched)} {untouched}")
    print(f"patch toca mais de 3 funções: {len(wide)} {wide}")
    print(f"casos com mais de uma função tocada: {sum(1 for r in rows if len(r['tocadas_pelo_patch']) > 1)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
