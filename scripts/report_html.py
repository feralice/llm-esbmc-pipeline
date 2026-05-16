from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_GT = REPO_ROOT / "examples" / "labeled" / "ground_truth.json"

_CLASS_META = {
    "formally_confirmed_bug":                        ("🐛 Bug Confirmado",        "#e74c3c", "#fdf2f2"),
    "vulnerability_potential_with_partial_evidence": ("⚠️ Suspeita",              "#e67e22", "#fef9f0"),
    "unconfirmed_hypothesis":                        ("🔍 Hipótese",              "#3498db", "#f0f7fd"),
    "smell_heuristic":                               ("👃 Smell",                 "#9b59b6", "#f8f4fd"),
    "inconclusive_case":                             ("❓ Inconclusivo",           "#7f8c8d", "#f5f5f5"),
}

_CONF_COLOR = {"high": "#27ae60", "medium": "#f39c12", "low": "#e74c3c"}
_ESBMC_META = {
    "violation_found":    ("VIOLAÇÃO ENCONTRADA", "#e74c3c"),
    "no_violation_found": ("SEM VIOLAÇÃO",         "#27ae60"),
    "skipped":            ("ESBMC não disponível", "#95a5a6"),
    "inconclusive":       ("INCONCLUSIVO",          "#f39c12"),
}

# verdict
_VERDICT = {
    "tp":       ("✅ Correto",                    "#27ae60", "#eafaf1"),
    "tp_wrong": ("⚠️ Detectou, verifiable errado", "#f39c12", "#fef9f0"),
    "fp":       ("❌ Falso positivo",              "#e74c3c", "#fdf2f2"),
    "fn":       ("🔴 Falso negativo (não detectou)","#c0392b","#fdf2f2"),
    "unknown":  ("",                               "",        ""),
}


# ---------------------------------------------------------------------------
# Ground truth helpers
# ---------------------------------------------------------------------------

def _load_ground_truth(gt_path: Path) -> dict:
    if not gt_path.exists():
        return {}
    return json.loads(gt_path.read_text(encoding="utf-8"))


def _gt_key(source_file: str) -> str:
    """Extrai o nome do arquivo para buscar no ground truth."""
    return Path(source_file).name


def _build_verdict_map(report: list[dict], ground_truth: dict) -> tuple[dict[int, str], list[dict]]:
    """
    Retorna:
    - verdict_map: {índice_finding → 'tp'|'tp_wrong'|'fp'|'unknown'}
    - missed: lista de expected findings não detectados (FN)
    """
    if not ground_truth:
        return {i: "unknown" for i in range(len(report))}, []

    verdict_map: dict[int, str] = {}
    missed: list[dict] = []

    # agrupa findings do report por arquivo
    by_file: dict[str, list[tuple[int, dict]]] = {}
    for i, r in enumerate(report):
        key = _gt_key(r.get("source_file", ""))
        by_file.setdefault(key, []).append((i, r))

    for filename, expected_list in ground_truth.items():
        if filename not in by_file:
            # arquivo não foi analisado nessa rodada — não conta como FN
            continue

        expected = expected_list.get("expected_findings", [])
        findings_for_file = by_file.get(filename, [])

        matched_expected: set[int] = set()
        matched_generated: set[int] = set()

        # tenta casar por categoria
        for ei, exp in enumerate(expected):
            for gi, (idx, r) in enumerate(findings_for_file):
                if gi in matched_generated:
                    continue
                if r["finding"].get("category") != exp.get("category"):
                    continue
                matched_expected.add(ei)
                matched_generated.add(gi)
                # verifiable correto?
                if r["finding"].get("verifiable") == exp.get("verifiable"):
                    verdict_map[idx] = "tp"
                else:
                    verdict_map[idx] = "tp_wrong"
                break

        # falsos positivos: gerados sem par no expected
        for gi, (idx, _) in enumerate(findings_for_file):
            if gi not in matched_generated:
                verdict_map[idx] = "fp"

        # falsos negativos: expected sem par gerado
        for ei, exp in enumerate(expected):
            if ei not in matched_expected:
                missed.append({**exp, "_file": filename})

    # findings de arquivos fora do ground truth → unknown
    for i in range(len(report)):
        if i not in verdict_map:
            verdict_map[i] = "unknown"

    return verdict_map, missed


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _badge(text: str, bg: str, fg: str = "white") -> str:
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 9px;'
        f'border-radius:12px;font-size:.75em;font-weight:700">{text}</span>'
    )


def _verdict_banner(verdict: str) -> str:
    if verdict == "unknown":
        return ""
    label, color, bg = _VERDICT[verdict]
    return (
        f'<div style="background:{bg};border-left:4px solid {color};'
        f'padding:7px 12px;border-radius:0 6px 6px 0;margin-bottom:10px;'
        f'font-weight:700;font-size:.88em;color:{color}">{label}</div>'
    )


def _card(result: dict, idx: int, verdict: str) -> str:
    cls = result.get("final_classification", "inconclusive_case")
    label, accent, bg = _CLASS_META.get(cls, ("?", "#7f8c8d", "#f5f5f5"))
    f = result["finding"]
    category    = f.get("category", "")
    conf        = f.get("confidence", "low")
    verifiable  = f.get("verifiable", False)
    explanation = f.get("explanation", "")
    evidence    = f.get("evidence", [])
    metadata    = f.get("metadata", {})
    expr        = metadata.get("expression", "")
    line        = metadata.get("line", "")
    unit        = result.get("unit_name", "")
    src         = result.get("source_file", "")
    interp      = result.get("interpretation", "")
    formal      = result.get("formal_property")
    esbmc       = result.get("esbmc_result")

    ev_html = "".join(
        f'<div class="code-snippet">{e}</div>' for e in evidence
    ) if evidence else ""

    formal_html = ""
    if formal:
        assertion = formal.get("assertion", "")
        flags = " ".join(formal.get("esbmc_flags", []))
        formal_html = f"""
        <div class="sub-block">
            <div class="block-title">📐 Propriedade Formal</div>
            <div class="code-snippet">assert {assertion}</div>
            {f'<div class="flags-line">flags: <code>{flags}</code></div>' if flags else ''}
        </div>"""

    esbmc_html = ""
    if esbmc:
        status  = esbmc.get("status", "")
        summary = esbmc.get("summary", "")
        slabel, scolor = _ESBMC_META.get(status, (status, "#7f8c8d"))
        details = esbmc.get("details", {})
        counter = details.get("counterexample", [])
        counter_html = ""
        if counter:
            items = "".join(f'<div class="code-snippet">{c}</div>' for c in counter)
            counter_html = f'<div class="block-title" style="margin-top:8px">Contraexemplo</div>{items}'
        esbmc_html = f"""
        <div class="sub-block" style="border-left:4px solid {scolor}">
            <div class="block-title">🔬 ESBMC</div>
            {_badge(slabel, scolor)}
            <span style="font-size:.85em;color:#555;margin-left:8px">{summary}</span>
            {counter_html}
        </div>"""

    conf_color = _CONF_COLOR.get(conf, "#7f8c8d")
    verif_badge = (
        _badge("verifiable ✓", "#27ae60")
        if verifiable else
        _badge("não verifiable", "#95a5a6", "#fff")
    )

    return f"""
    <div class="card" data-cls="{cls}" data-verifiable="{str(verifiable).lower()}" data-verdict="{verdict}" id="card-{idx}">
        <div class="card-header" style="background:{accent}">
            <span class="card-label">{label}</span>
            <span class="card-unit">{unit} <small>— {src}</small></span>
        </div>
        <div class="card-body" style="background:{bg}">
            {_verdict_banner(verdict)}
            <div class="tags">
                {verif_badge}
                {_badge(f"confiança: {conf}", conf_color)}
                {_badge(category, "#636e72", "#fff")}
                {f'<span style="font-size:.8em;color:#7f8c8d">linha {line}</span>' if line else ''}
            </div>
            <p class="explanation">{explanation}</p>
            {ev_html}
            {f'<div class="expr-line">Expressão: <code>{expr}</code></div>' if expr else ''}
            {formal_html}
            {esbmc_html}
            <div class="interpretation">{interp}</div>
        </div>
    </div>"""


def _missed_section(missed: list[dict]) -> str:
    if not missed:
        return ""
    items = "".join(
        f'<div class="missed-item">'
        f'🔴 <strong>{m.get("category","")}</strong> em '
        f'<code>{m.get("function","?")}</code> '
        f'({m.get("_file","")})'
        f'</div>'
        for m in missed
    )
    return f"""
    <div class="section-title">Falsos negativos (não detectados)</div>
    <div class="missed-box">{items}</div>"""


def _summary_row(result: dict, verdict: str) -> str:
    cls = result.get("final_classification", "")
    label, accent, _ = _CLASS_META.get(cls, ("?", "#7f8c8d", ""))
    f   = result["finding"]
    cat = f.get("category", "")
    conf= f.get("confidence", "")
    ver = "✓" if f.get("verifiable") else "✗"
    cc  = _CONF_COLOR.get(conf, "#7f8c8d")
    vc  = _VERDICT.get(verdict, ("", "", ""))
    verdict_cell = f'<span style="color:{vc[1]};font-weight:700">{vc[0]}</span>' if vc[0] else "—"
    return f"""
    <tr>
        <td><code>{result.get("unit_name","")}</code></td>
        <td>{_badge(cat, "#636e72")}</td>
        <td style="text-align:center;color:{'#27ae60' if f.get('verifiable') else '#e74c3c'};font-weight:bold">{ver}</td>
        <td>{_badge(conf, cc)}</td>
        <td>{_badge(label, accent)}</td>
        <td>{verdict_cell}</td>
    </tr>"""


def generate_html(report: list[dict], source_label: str, ground_truth: dict | None = None) -> str:
    gt = ground_truth or {}
    verdict_map, missed = _build_verdict_map(report, gt)

    total    = len(report)
    n_bug    = sum(1 for r in report if r["final_classification"] == "formally_confirmed_bug")
    n_sus    = sum(1 for r in report if r["final_classification"] == "vulnerability_potential_with_partial_evidence")
    n_smell  = sum(1 for r in report if r["final_classification"] == "smell_heuristic")
    n_unconf = sum(1 for r in report if r["final_classification"] == "unconfirmed_hypothesis")
    n_verif  = sum(1 for r in report if r["finding"].get("verifiable"))

    n_tp       = sum(1 for v in verdict_map.values() if v == "tp")
    n_tp_wrong = sum(1 for v in verdict_map.values() if v == "tp_wrong")
    n_fp       = sum(1 for v in verdict_map.values() if v == "fp")
    n_fn       = len(missed)
    has_gt     = bool(gt)

    cards_html = "\n".join(_card(r, i, verdict_map.get(i, "unknown")) for i, r in enumerate(report))
    rows       = "".join(_summary_row(r, verdict_map.get(i, "unknown")) for i, r in enumerate(report))
    missed_html = _missed_section(missed)

    gt_stats = f"""
    <div class="stat-card"><span class="num" style="color:#27ae60">{n_tp}</span><div class="lbl">✅ Corretos (TP)</div></div>
    <div class="stat-card"><span class="num" style="color:#f39c12">{n_tp_wrong}</span><div class="lbl">⚠️ Verifiable errado</div></div>
    <div class="stat-card"><span class="num" style="color:#e74c3c">{n_fp}</span><div class="lbl">❌ Falsos positivos</div></div>
    <div class="stat-card"><span class="num" style="color:#c0392b">{n_fn}</span><div class="lbl">🔴 Não detectados (FN)</div></div>
    """ if has_gt else ""

    filter_verdict = """
    <button class="filter-btn" onclick="filter('tp')">✅ Corretos</button>
    <button class="filter-btn" onclick="filter('tp_wrong')">⚠️ Verifiable errado</button>
    <button class="filter-btn" onclick="filter('fp')">❌ Falsos positivos</button>
    """ if has_gt else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LLM+ESBMC — Relatório</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f0f2f5; color: #2c3e50; min-height: 100vh;
  }}
  header {{
    background: linear-gradient(135deg, #2c3e50, #3498db);
    color: white; padding: 28px 40px;
  }}
  header h1 {{ font-size: 1.6em; font-weight: 700; }}
  header p  {{ opacity: .75; font-size: .9em; margin-top: 4px; }}
  .container {{ max-width: 1000px; margin: 0 auto; padding: 28px 20px; }}

  .stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 28px; }}
  .stat-card {{
    background: white; border-radius: 10px; padding: 16px 22px;
    box-shadow: 0 1px 6px rgba(0,0,0,.08); flex: 1; min-width: 110px; text-align: center;
  }}
  .stat-card .num {{ font-size: 2em; font-weight: 800; display: block; }}
  .stat-card .lbl {{ font-size: .78em; color: #7f8c8d; margin-top: 2px; }}

  .divider {{ height: 1px; background: #dee2e6; margin: 20px 0; }}

  .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }}
  .filter-btn {{
    border: 2px solid #dee2e6; background: white; border-radius: 20px;
    padding: 5px 14px; font-size: .82em; cursor: pointer; font-weight: 600;
    transition: all .15s; color: #555;
  }}
  .filter-btn:hover, .filter-btn.active {{
    border-color: #3498db; background: #3498db; color: white;
  }}

  .section-title {{ font-size: 1.1em; font-weight: 700; margin: 24px 0 10px; color: #2c3e50; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 10px; overflow: hidden;
           box-shadow: 0 1px 6px rgba(0,0,0,.08); margin-bottom: 28px; }}
  th {{ background: #2c3e50; color: white; padding: 10px 14px; text-align: left; font-size: .82em; }}
  td {{ padding: 8px 14px; border-bottom: 1px solid #f0f2f5; font-size: .88em; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8f9fa; }}

  .card {{
    background: white; border-radius: 10px; margin-bottom: 14px;
    box-shadow: 0 1px 6px rgba(0,0,0,.08); overflow: hidden; transition: box-shadow .15s;
  }}
  .card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,.12); }}
  .card.hidden {{ display: none; }}
  .card-header {{
    padding: 10px 16px; display: flex; justify-content: space-between;
    align-items: center; color: white;
  }}
  .card-label {{ font-weight: 700; font-size: .92em; }}
  .card-unit  {{ font-size: .8em; opacity: .9; }}
  .card-body  {{ padding: 14px 16px; }}

  .tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }}

  .explanation {{ font-size: .9em; color: #444; line-height: 1.55; margin: 8px 0; }}
  .code-snippet {{
    background: #1e272e; color: #dfe6e9;
    font-family: "Fira Code", "Courier New", monospace;
    font-size: .82em; padding: 7px 12px; border-radius: 5px;
    margin: 4px 0; white-space: pre-wrap; word-break: break-all;
  }}
  .expr-line {{ font-size: .83em; color: #7f8c8d; margin: 6px 0; }}
  .expr-line code {{ background: #eee; padding: 1px 5px; border-radius: 3px; color: #2c3e50; }}

  .sub-block {{
    margin-top: 12px; padding: 10px 12px; border-radius: 6px; background: #f8f9fa;
  }}
  .block-title {{
    font-size: .78em; font-weight: 700; color: #7f8c8d;
    text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px;
  }}
  .flags-line {{ font-size: .78em; color: #7f8c8d; margin-top: 5px; }}
  .interpretation {{
    margin-top: 10px; font-size: .82em; color: #7f8c8d;
    border-top: 1px solid #eee; padding-top: 8px; font-style: italic;
  }}

  .missed-box {{
    background: white; border-radius: 10px; padding: 14px 18px;
    box-shadow: 0 1px 6px rgba(0,0,0,.08); margin-bottom: 28px;
  }}
  .missed-item {{
    padding: 7px 0; border-bottom: 1px solid #f0f2f5;
    font-size: .9em; color: #444;
  }}
  .missed-item:last-child {{ border-bottom: none; }}

  footer {{ text-align: center; color: #bdc3c7; font-size: .78em; padding: 24px 0; }}
</style>
</head>
<body>

<header>
  <h1>🔍 LLM + ESBMC — Relatório de Análise</h1>
  <p>{source_label}</p>
</header>

<div class="container">

  <div class="stats">
    <div class="stat-card"><span class="num" style="color:#2c3e50">{total}</span><div class="lbl">Total findings</div></div>
    <div class="stat-card"><span class="num" style="color:#e74c3c">{n_bug}</span><div class="lbl">🐛 Bugs confirmados</div></div>
    <div class="stat-card"><span class="num" style="color:#e67e22">{n_sus}</span><div class="lbl">⚠️ Suspeitas</div></div>
    <div class="stat-card"><span class="num" style="color:#9b59b6">{n_smell}</span><div class="lbl">👃 Smells</div></div>
    <div class="stat-card"><span class="num" style="color:#27ae60">{n_verif}</span><div class="lbl">Verificáveis</div></div>
  </div>

  {f'<div class="divider"></div><div class="section-title">📊 Comparação com Ground Truth</div><div class="stats">{gt_stats}</div>' if has_gt else ''}

  <div class="section-title">Resumo</div>
  <table>
    <tr>
      <th>Função</th><th>Categoria</th>
      <th style="text-align:center">Verifiable</th>
      <th>Confiança</th><th>Classificação</th>
      {'<th>Ground Truth</th>' if has_gt else ''}
    </tr>
    {rows}
  </table>

  {missed_html}

  <div class="section-title">Findings detalhados</div>
  <div class="filters">
    <button class="filter-btn active" onclick="filter('all')">Todos ({total})</button>
    <button class="filter-btn" onclick="filter('formally_confirmed_bug')">🐛 Bugs ({n_bug})</button>
    <button class="filter-btn" onclick="filter('vulnerability_potential_with_partial_evidence')">⚠️ Suspeitas ({n_sus})</button>
    <button class="filter-btn" onclick="filter('smell_heuristic')">👃 Smells ({n_smell})</button>
    <button class="filter-btn" onclick="filter('verifiable')">✓ Verificáveis ({n_verif})</button>
    {filter_verdict}
  </div>

  <div id="cards">
{cards_html}
  </div>

</div>

<footer>Gerado por llm-esbmc-pipeline</footer>

<script>
function filter(cls) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.card').forEach(card => {{
    if (cls === 'all') {{
      card.classList.remove('hidden');
    }} else if (cls === 'verifiable') {{
      card.classList.toggle('hidden', card.dataset.verifiable !== 'true');
    }} else if (['tp','tp_wrong','fp'].includes(cls)) {{
      card.classList.toggle('hidden', card.dataset.verdict !== cls);
    }} else {{
      card.classList.toggle('hidden', card.dataset.cls !== cls);
    }}
  }});
}}
</script>
</body>
</html>"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera relatório HTML a partir do report.json do pipeline.",
    )
    parser.add_argument(
        "--input",
        default=str(REPO_ROOT / "artifacts" / "research-pipeline" / "report.json"),
        help="Caminho do report.json.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Caminho do HTML de saída. (padrão: mesmo dir do input)",
    )
    parser.add_argument(
        "--ground-truth",
        default=str(_DEFAULT_GT),
        help="Caminho do ground_truth.json para comparação. (padrão: examples/labeled/ground_truth.json)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Erro: {input_path} não encontrado.", file=sys.stderr)
        return 1

    report = json.loads(input_path.read_text(encoding="utf-8"))
    gt = _load_ground_truth(Path(args.ground_truth))
    output_path = Path(args.output) if args.output else input_path.with_suffix(".html")

    html = generate_html(report, str(input_path), gt)
    output_path.write_text(html, encoding="utf-8")
    print(f"Relatório HTML salvo em: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
