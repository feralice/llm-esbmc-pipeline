"""Ablacao de flags do ESBMC: testa parametros alternativos alem do
--assign-param-nondet fixo (docs/projeto/cronograma_pesquisa.csv, "Testar parametros
alternativos de verificacao no ESBMC"). Sem custo de API: so reroda ESBMC
sobre os harnesses reais ja sintetizados em artifacts/v2/driver-slice-117-rerun,
cobrindo as 8 categorias formais.

Uso:
  PYTHONPATH=src .venv/bin/python scripts/esbmc_flag_ablation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from research_pipeline.verification.esbmc_runner import run_esbmc_direct

REPORT_PATH = Path("artifacts/v2/driver-slice-117-rerun/v2_report.json")
OUT_DIR = Path("artifacts/flag_ablation_logs")

GENERIC_VARIANTS: dict[str, list[str]] = {
    "baseline": [],
    "no_slice": ["--no-slice"],
    "ir_solver": ["--ir"],
}
CATEGORY_VARIANTS: dict[str, tuple[str, list[str]]] = {
    "type_mismatch": ("strict_types", ["--strict-types"]),
    "integer_overflow": ("unsigned_overflow_check", ["--unsigned-overflow-check"]),
}


def main(bound: int = 5, timeout: int = 20) -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    results = report["results"]

    summary: dict[str, dict[str, int]] = {}
    per_case: list[dict] = []

    for entry in results:
        category = entry["candidate"]["category"]
        harness_path = entry.get("harness_path")
        if not harness_path or not Path(harness_path).exists():
            continue

        variants = dict(GENERIC_VARIANTS)
        if category in CATEGORY_VARIANTS:
            name, flags = CATEGORY_VARIANTS[category]
            variants[name] = flags

        row = {"case": Path(harness_path).stem, "category": category, "classification": entry["classification"]}
        for variant_name, extra_flags in variants.items():
            result = run_esbmc_direct(
                file_path=harness_path,
                esbmc_command=["esbmc", *extra_flags],
                bound=bound,
                timeout_seconds=timeout,
                output_dir=str(OUT_DIR),
            )
            row[variant_name] = result.status
            summary.setdefault(variant_name, {})
            summary[variant_name][result.status] = summary[variant_name].get(result.status, 0) + 1
        per_case.append(row)
        print(f"[{len(per_case)}/{len(results)}] {row}")

    print("\n=== Resumo por variante ===")
    for variant_name, counts in summary.items():
        print(f"{variant_name:22s} {counts}")

    print("\n=== Casos onde uma variante de categoria mudou o veredito do baseline ===")
    for row in per_case:
        for special in ("strict_types", "unsigned_overflow_check"):
            if special in row and row[special] != row["baseline"]:
                print(f"  {row}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(
        json.dumps({"summary": summary, "per_case": per_case}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSalvo em {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
