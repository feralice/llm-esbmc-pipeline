"""Lista, em uma tabela, o modelo, o backend e os tokens de cada rodada gravada (sem chamar LLM).

Lê v2_verify_report.json (dataset) e scan_report.json (scan) sob as pastas dadas e escreve um .md.
Uso: python scripts/registro_rodadas.py PASTA [PASTA ...] --out docs/experimentos/REGISTRO_MODELOS_TOKENS.md
Tokens de detecção e de síntese vêm da telemetria do próprio relatório; onde ela não existe, a célula fica "n/d".
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

HEADER = ("| Pasta | Data | Tipo | Modelo | Backend | Variantes | Hipóteses | Tokens detecção | Tokens síntese/spec |\n"
          "|---|---|---|---|---|---|---:|---:|---:|")


def _row(path: Path) -> list[str] | None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict):
        return None
    config = report.get("config") or {}
    when = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    if path.name == "scan_report.json":
        detection = report.get("detection") or {}
        model = config.get("model", "n/d")
        cells = ["scan", model, "n/d", ",".join(config.get("variants") or []), str(detection.get("hypotheses", "n/d")),
                 str(detection.get("tokens", "n/d")), str(report.get("verification_tokens") or "n/d")]
    else:
        telemetry = report.get("telemetry") or {}
        detection = report.get("detection") or {}
        synth = config.get("synth_model")
        model = config.get("model", "n/d") + (f" (síntese {synth})" if synth and synth != config.get("model") else "")
        cells = ["dataset", model, str(config.get("backend", "n/d")), ",".join(config.get("v2_variants") or []),
                 str(detection.get("hypotheses", "n/d")),
                 str((telemetry.get("detection") or {}).get("tokens", "n/d")),
                 str((telemetry.get("synthesis") or {}).get("tokens", "n/d"))]
    return [path.parent.name, when, *cells]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for root in args.roots:
        for name in ("v2_verify_report.json", "scan_report.json"):
            rows += [r for p in sorted(root.rglob(name)) if (r := _row(p))]
    rows = [list(r) for r in dict.fromkeys(tuple(r) for r in rows)]
    rows.sort(key=lambda r: (r[1], r[0]))
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    args.out.write_text("# Modelos e tokens de cada rodada\n\nGerado por scripts/registro_rodadas.py a partir dos "
                        "relatórios gravados. Backend claude_cli usa a assinatura: o custo em dólar não existe, "
                        "só tokens.\n\n" + HEADER + "\n" + body + "\n", encoding="utf-8")
    print(f"{len(rows)} rodadas em {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
