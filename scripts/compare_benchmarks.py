"""
Lê os JSONs de benchmark do V1 e imprime a tabela comparativa.

Uso:
    python3 scripts/compare_benchmarks.py --dir reports/json/v1_benchmark
    python3 scripts/compare_benchmarks.py --dir reports/json/v1_benchmark --latex
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_reports(directory: Path, suffix: str) -> list[dict]:
    reports = []
    for path in sorted(directory.glob(f"benchmark_*_{suffix}.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_file"] = path.name
        reports.append(data)
    return reports


def short_name(model_label: str) -> str:
    name = model_label.split("/")[-1]
    replacements = {
        "gpt-4o-2024-11-20": "GPT-4o",
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
        "qwen2.5-coder:7b": "Qwen2.5-Coder-7B",
        "qwen2.5-coder:32b": "Qwen2.5-Coder-32B",
    }
    return replacements.get(name, name)


def fmt(value: float | None, *, na: str = "N/A") -> str:
    if value is None:
        return na
    return f"{value:.4f}"


def print_table(title: str, reports: list[dict], section: str, latex: bool) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

    if not reports:
        print("  (nenhum relatório encontrado)")
        return

    headers = ["Model", "Precision", "Recall", "F1", "TP", "FP", "FN"]
    rows = []

    for r in reports:
        metrics = r.get("metrics", {}).get(section, {})
        if not metrics:
            continue
        name = short_name(r.get("model", r["_file"]))
        p = metrics.get("precision")
        rec = metrics.get("recall")
        f1 = metrics.get("f1")
        tp = metrics.get("tp", "-")
        fp = metrics.get("fp", "-")
        fn = metrics.get("fn", "-")

        # esbmc_direct_baseline: precision é indefinida se tp+fp=0
        if section == "esbmc_direct_baseline" and tp == 0 and fp == 0:
            p_str = "N/A"
        else:
            p_str = fmt(p)

        rows.append([name, p_str, fmt(rec), fmt(f1), str(tp), str(fp), str(fn)])

    if not rows:
        print("  (sem dados nesta seção)")
        return

    if latex:
        _print_latex(headers, rows)
    else:
        _print_ascii(headers, rows)


def _print_ascii(headers: list[str], rows: list[list[str]]) -> None:
    col_w = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    sep = "+-" + "-+-".join("-" * w for w in col_w) + "-+"
    fmt_row = lambda cells: "| " + " | ".join(c.ljust(w) for c, w in zip(cells, col_w)) + " |"
    print(sep)
    print(fmt_row(headers))
    print(sep)
    for row in rows:
        print(fmt_row(row))
    print(sep)


def _print_latex(headers: list[str], rows: list[list[str]]) -> None:
    print(r"\begin{tabular}{l" + "r" * (len(headers) - 1) + "}")
    print(r"\toprule")
    print(" & ".join(headers) + r" \\")
    print(r"\midrule")
    for row in rows:
        print(" & ".join(row) + r" \\")
    print(r"\bottomrule")
    print(r"\end{tabular}")


def print_per_category(reports: list[dict], latex: bool) -> None:
    categories = ["assertion_violation", "division_by_zero", "out_of_bounds"]
    print(f"\n{'='*70}")
    print("  LLM-only — por categoria")
    print(f"{'='*70}")

    headers = ["Model", "Category", "P", "R", "F1", "TP", "FP", "FN"]
    rows = []
    for r in reports:
        name = short_name(r.get("model", r["_file"]))
        per_cat = r.get("per_category", {})
        for cat in categories:
            m = per_cat.get(cat, {})
            if not m:
                continue
            rows.append([
                name,
                cat.replace("_", " "),
                fmt(m.get("precision")),
                fmt(m.get("recall")),
                fmt(m.get("f1")),
                str(m.get("tp", "-")),
                str(m.get("fp", "-")),
                str(m.get("fn", "-")),
            ])

    if rows:
        if latex:
            _print_latex(headers, rows)
        else:
            _print_ascii(headers, rows)
    else:
        print("  (sem dados per_category)")


def print_esbmc_note(reports: list[dict]) -> None:
    for r in reports:
        m = r.get("metrics", {}).get("esbmc_direct_baseline", {})
        if m.get("tp", 0) == 0 and m.get("fp", 0) == 0:
            print("\n  Nota: ESBMC direto gerou 0 VCCs em todos os arquivos.")
            print("        Precision = N/A (sem detecções); Recall = 0.00.")
            return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="reports/json/v1_benchmark",
                        help="Diretório com os JSONs de benchmark")
    parser.add_argument("--latex", action="store_true",
                        help="Imprime tabelas em formato LaTeX")
    args = parser.parse_args()

    directory = Path(args.dir)
    if not directory.exists():
        print(f"Diretório não encontrado: {directory}")
        return

    bugs = load_reports(directory, "bugs")
    smells = load_reports(directory, "smells")

    print(f"\nRelatórios carregados: {len(bugs)} bugs, {len(smells)} smells")

    if bugs:
        print_table("Bugs — LLM only",         bugs, "bugs_llm_only",          args.latex)
        print_table("Bugs — Hybrid (LLM+ESBMC)", bugs, "bugs_hybrid_pipeline",  args.latex)
        print_table("ESBMC direto (baseline)",  bugs, "esbmc_direct_baseline",  args.latex)
        print_esbmc_note(bugs)
        print_per_category(bugs, args.latex)

    if smells:
        print_table("Smells — LLM only", smells, "smells", args.latex)

    # resumo de hallucinations
    if bugs:
        print(f"\n{'='*70}")
        print("  Hallucination rate (achados inválidos descartados pelo AST validator)")
        print(f"{'='*70}")
        headers = ["Model", "Count", "Rate"]
        rows = []
        for r in bugs:
            h = r.get("hallucinations", {})
            rows.append([
                short_name(r.get("model", r["_file"])),
                str(h.get("count", "-")),
                fmt(h.get("rate")),
            ])
        _print_ascii(headers, rows)


if __name__ == "__main__":
    main()
