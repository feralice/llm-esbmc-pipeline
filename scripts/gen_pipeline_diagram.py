"""Generate the current V2 pipeline diagram as an SVG.

The old V1 diagram is preserved at docs/v1/pipeline_flow_diagram_v1.svg.
This script renders the active --mode v2 flow implemented by src/main.py and
research_pipeline/scan/.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

W, H = 1280, 780
FONT = "Arial, Helvetica, sans-serif"
OUT = Path("docs/v2/pipeline_atual_v2.svg")

lines: list[str] = []


def add(raw: str) -> None:
    lines.append(raw)


def rect(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    rx: int = 8,
    fill: str = "#fff",
    stroke: str = "#c9cdd2",
    sw: float = 1.4,
) -> None:
    add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    )


def text(
    x: int,
    y: int,
    value: str,
    *,
    size: int = 14,
    weight: str = "400",
    fill: str = "#1f2933",
    anchor: str = "middle",
) -> None:
    add(
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
        f"{escape(value)}</text>"
    )


def multiline(
    x: int,
    y: int,
    rows: list[str],
    *,
    size: int = 13,
    line_h: int = 18,
    fill: str = "#3f4d5a",
    anchor: str = "middle",
) -> None:
    for idx, row in enumerate(rows):
        text(x, y + idx * line_h, row, size=size, fill=fill, anchor=anchor)


def _marker(marker_id: str, color: str) -> None:
    add(
        f'<defs><marker id="{marker_id}" markerWidth="10" markerHeight="10" '
        f'refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L0,6 L9,3 z" fill="{color}"/></marker></defs>'
    )


def arrow(x1: int, y1: int, x2: int, y2: int, *, color: str = "#6b7280") -> None:
    marker_id = f"arrow-{x1}-{y1}-{x2}-{y2}"
    _marker(marker_id, color)
    add(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        f'stroke-width="2" marker-end="url(#{marker_id})"/>'
    )


def dashed_arrow(x1: int, y1: int, x2: int, y2: int, *, color: str = "#8b949e") -> None:
    marker_id = f"darrow-{x1}-{y1}-{x2}-{y2}"
    _marker(marker_id, color)
    add(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        f'stroke-width="1.8" stroke-dasharray="6,5" marker-end="url(#{marker_id})"/>'
    )


def box(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    rows: list[str],
    *,
    fill: str,
    stroke: str,
    title_fill: str = "#102a43",
) -> None:
    add(f'<rect x="{x + 3}" y="{y + 4}" width="{w}" height="{h}" rx="9" fill="#000" opacity="0.08"/>')
    rect(x, y, w, h, rx=9, fill=fill, stroke=stroke, sw=1.8)
    text(x + w // 2, y + 27, title, size=15, weight="700", fill=title_fill)
    add(
        f'<line x1="{x + 18}" y1="{y + 42}" x2="{x + w - 18}" y2="{y + 42}" '
        f'stroke="{stroke}" opacity="0.35"/>'
    )
    multiline(x + w // 2, y + 64, rows, size=12, line_h=17)


def small_label(x: int, y: int, value: str, *, fill: str = "#52616f") -> None:
    rect(x - 78, y - 14, 156, 24, rx=12, fill="#ffffff", stroke="#d9dee5", sw=1)
    text(x, y + 3, value, size=11, fill=fill)


add(
    f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
    f'xmlns="http://www.w3.org/2000/svg">'
)
rect(0, 0, W, H, rx=0, fill="#f6f8fb", stroke="none", sw=0)

text(
    W // 2,
    38,
    "Pipeline atual V2: deteccao LLM -> harness -> ESBMC",
    size=24,
    weight="700",
    fill="#102a43",
)
text(
    W // 2,
    62,
    "Fluxo implementado por src/main.py --mode v2 e research_pipeline/scan/",
    size=13,
    fill="#52616f",
)

box(
    48,
    105,
    205,
    112,
    "1. Entrada",
    ["dataset/v2_real_world/detection", "arquivos Python reais", "sem ground truth no prompt"],
    fill="#e9f7ef",
    stroke="#2f855a",
    title_fill="#276749",
)
box(
    302,
    105,
    205,
    112,
    "2. AST",
    ["preprocess_file()", "gera CodeUnit", "funcao, parametros, fonte"],
    fill="#eef6ff",
    stroke="#2b6cb0",
    title_fill="#2b6cb0",
)
box(
    556,
    105,
    205,
    112,
    "3. Deteccao",
    ["analyzer.analyze(unit)", "LLM retorna findings JSON", "backend escolhido"],
    fill="#fff7ed",
    stroke="#c05621",
    title_fill="#c05621",
)
box(
    810,
    105,
    205,
    112,
    "4. Filtro",
    ["mantem suspected_bug", "exige verifiable=true", "rejeita smell/fora de escopo"],
    fill="#fdf2f8",
    stroke="#b83280",
    title_fill="#97266d",
)
box(
    1064,
    105,
    168,
    112,
    "5. Candidatos",
    ["ScanCandidate", "file + function", "category + expression"],
    fill="#f0f4f8",
    stroke="#627d98",
)

for x1 in (253, 507, 761, 1015):
    arrow(x1, 161, x1 + 49, 161)

box(
    595,
    262,
    380,
    86,
    "Rejeicoes da deteccao",
    ["llm_false_positive, out_of_scope_finding, smell heuristico", "checkpoint: rejected_findings"],
    fill="#fff1f2",
    stroke="#c53030",
    title_fill="#9b2c2c",
)
dashed_arrow(912, 217, 790, 262, color="#c53030")
small_label(820, 244, "nao vira harness", fill="#9b2c2c")

text(640, 395, "Etapa 2: verificacao por camadas, uma hipotese por vez", size=17, weight="700", fill="#102a43")

box(
    58,
    440,
    248,
    118,
    "Tier A: nativo",
    ["run_esbmc_on_function()", "ESBMC --function na funcao real", "sem harness LLM"],
    fill="#e6fffa",
    stroke="#2c7a7b",
    title_fill="#285e61",
)
box(
    366,
    440,
    248,
    118,
    "Tier B: driver",
    ["LLM mantem funcao real intacta", "gera so driver simbolico", "check_driver_harness()"],
    fill="#ebf8ff",
    stroke="#3182ce",
    title_fill="#2b6cb0",
)
box(
    674,
    440,
    248,
    118,
    "Tier C: escalar",
    ["LLM sintetiza harness abstrato", "guards.py limita precondicoes", "check_harness() valida compatibilidade"],
    fill="#faf5ff",
    stroke="#805ad5",
    title_fill="#6b46c1",
)
box(
    982,
    440,
    248,
    118,
    "ESBMC + ablation",
    ["run_esbmc_direct()", "SUCCESSFUL -> remove assumes", "detecta over_restricted"],
    fill="#fffaf0",
    stroke="#d69e2e",
    title_fill="#b7791f",
)

arrow(1148, 217, 182, 440, color="#627d98")
arrow(306, 499, 366, 499, color="#627d98")
small_label(337, 484, "se inconclusivo")
arrow(614, 499, 674, 499, color="#627d98")
small_label(644, 484, "fallback")
arrow(922, 499, 982, 499, color="#627d98")

box(
    80,
    620,
    295,
    88,
    "Confirmado",
    ["confirmed_native / confirmed_driver", "confirmed_on_abstraction"],
    fill="#ecfdf5",
    stroke="#38a169",
    title_fill="#276749",
)
box(
    492,
    620,
    295,
    88,
    "Seguro ou mascarado",
    ["safe_native / safe_driver / safe_on_abstraction", "over_restricted quando ablation acha mascara"],
    fill="#fffbeb",
    stroke="#d69e2e",
    title_fill="#975a16",
)
box(
    904,
    620,
    295,
    88,
    "Inconclusivo",
    ["invalid_harness / unsupported_harness", "no_property / timeout / synth_failed"],
    fill="#fef2f2",
    stroke="#e53e3e",
    title_fill="#9b2c2c",
)

dashed_arrow(182, 558, 227, 620, color="#38a169")
dashed_arrow(490, 558, 227, 620, color="#38a169")
dashed_arrow(798, 558, 640, 620, color="#d69e2e")
dashed_arrow(1106, 558, 640, 620, color="#d69e2e")
dashed_arrow(798, 558, 1052, 620, color="#e53e3e")

rect(154, 735, 972, 32, rx=8, fill="#ffffff", stroke="#cbd5e0", sw=1.3)
text(
    640,
    756,
    "Artefatos: v2_checkpoint.json + v2_report.json + llm_telemetry.json; ground truth entra so na avaliacao final",
    size=13,
    weight="700",
    fill="#334e68",
)

add("</svg>")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Saved {OUT}")
