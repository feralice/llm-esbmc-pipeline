"""Minimal poster-style pipeline diagram — 3 big boxes, big text."""

W, H = 840, 450
FONT = "Arial, Helvetica, sans-serif"

lines = []
lines.append(f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
             f'xmlns="http://www.w3.org/2000/svg" '
             f'style="background:#F8F9FA">')

def rect(x, y, w, h, rx=10, fill="#fff", stroke="#ccc", sw=1.5):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

def t(x, y, s, sz=13, bold=False, col="#222", anchor="middle"):
    fw = "bold" if bold else "normal"
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'font-size="{sz}" font-weight="{fw}" fill="{col}" '
            f'font-family="{FONT}">{s}</text>')

def arrow_down(x, y1, y2, col="#999", sw=1.8):
    ey = y2 - 9
    tip = f"{x},{y2} {x-5},{ey} {x+5},{ey}"
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{ey}" '
            f'stroke="{col}" stroke-width="{sw}"/>'
            f'<polygon points="{tip}" fill="{col}"/>')

# ── background ─────────────────────────────────────────────────────
lines.append(rect(0, 0, W, H, 0, "#F8F9FA", "none"))

# ── title ──────────────────────────────────────────────────────────
lines.append(t(W//2, 38, "Pipeline LLM + ESBMC", 22, True, "#1A252F"))
lines.append(t(W//2, 60, "Comparação de três estratégias para detecção de bugs em Python",
               12, False, "#666"))

# ── shared input ───────────────────────────────────────────────────
lines.append(rect(160, 74, 520, 44, 8, "#EBF3FB", "#2471A3", 1.8))
lines.append(t(W//2, 92, "Entrada", 9, True, "#2471A3"))
lines.append(t(W//2, 108, "70 funções Python  ·  45 bugs formais  ·  15 code smells  ·  10 clean",
               11, False, "#1A5276"))

# ── fan arrows ─────────────────────────────────────────────────────
lines.append(arrow_down(215, 118, 155, "#2471A3"))
lines.append(arrow_down(W//2, 118, 155, "#2471A3"))
lines.append(arrow_down(625, 118, 155, "#2471A3"))

# ── three flow boxes ───────────────────────────────────────────────
BOX_W, BOX_H = 228, 198
BY = 158  # top of boxes
CXS = [120, W//2, 720]  # centers

FLOWS = [
    # (label, color_header, color_bg, color_border, lines_of_body)
    (
        "Flow A  —  ESBMC puro",
        "#1E8449", "#E9F7EF", "#1E8449",
        [
            ("ESBMC verifica diretamente", 13, True, "#1E8449"),
            ("sem nenhuma dica da LLM", 11, False, "#555"),
            ("", 8, False, "#fff"),
            ("→  esbmc_native_bug", 11, True, "#C0392B"),
            ("→  not_confirmed", 10, False, "#888"),
        ]
    ),
    (
        "Flow B  —  LLM + ESBMC",
        "#CA6F1E", "#FEF5E7", "#CA6F1E",
        [
            ("LLM sugere a categoria do bug", 13, True, "#CA6F1E"),
            ("ESBMC confirma formalmente", 11, False, "#555"),
            ("", 8, False, "#fff"),
            ("bugs formais  →  ESBMC", 11, True, "#1E8449"),
            ("code smells   →  heurística", 11, True, "#8E44AD"),
        ]
    ),
    (
        "Flow C  —  LLM puro",
        "#7D3C98", "#F5EEF8", "#7D3C98",
        [
            ("LLM sugere a categoria do bug", 13, True, "#7D3C98"),
            ("sem verificação formal", 11, False, "#555"),
            ("", 8, False, "#fff"),
            ("→  llm_only_suspected", 11, True, "#B7950B"),
            ("→  heuristic_smell_only", 11, True, "#8E44AD"),
        ]
    ),
]

for (cx, (label, hcol, bg, bd, body_lines)) in zip(CXS, FLOWS):
    x = cx - BOX_W // 2
    # shadow
    lines.append(rect(x+3, BY+3, BOX_W, BOX_H, 10, "#0002", "none"))
    # box
    lines.append(rect(x, BY, BOX_W, BOX_H, 10, bg, bd, 1.8))
    # header bar
    lines.append(f'<rect x="{x}" y="{BY}" width="{BOX_W}" height="38" '
                 f'rx="10" fill="{hcol}"/>')
    lines.append(f'<rect x="{x}" y="{BY+18}" width="{BOX_W}" height="20" fill="{hcol}"/>')
    lines.append(t(cx, BY + 25, label, 12, True, "white"))
    # divider
    lines.append(f'<line x1="{x+14}" y1="{BY+40}" x2="{x+BOX_W-14}" y2="{BY+40}" '
                 f'stroke="{bd}" stroke-width="0.8" opacity="0.4"/>')
    # body lines
    ty = BY + 60
    for (s, sz, bold, col) in body_lines:
        lines.append(t(cx, ty, s, sz, bold, col))
        ty += sz + 7

# ── bottom arrows ──────────────────────────────────────────────────
EVAL_Y = BY + BOX_H + 46

lines.append(arrow_down(CXS[0], BY + BOX_H, EVAL_Y - 2, "#1E8449"))
lines.append(arrow_down(CXS[1], BY + BOX_H, EVAL_Y - 2, "#CA6F1E"))
lines.append(arrow_down(CXS[2], BY + BOX_H, EVAL_Y - 2, "#7D3C98"))

# horizontal collector
lines.append(f'<line x1="{CXS[0]}" y1="{EVAL_Y-30}" x2="{CXS[2]}" y2="{EVAL_Y-30}" '
             f'stroke="#bbb" stroke-width="1.3" stroke-dasharray="4,3"/>')

# ── evaluator ──────────────────────────────────────────────────────
lines.append(rect(140, EVAL_Y, 560, 56, 9, "#EBF3FB", "#1A5276", 2))
lines.append(t(W//2, EVAL_Y + 24, "Avaliação contra ground truth", 14, True, "#1A5276"))
lines.append(t(W//2, EVAL_Y + 44,
               "Precision  ·  Recall  ·  F1  ·  MCC  ·  FCR  ·  NRR   (bootstrap CI 95%)",
               10.5, False, "#1A5276"))

lines.append("</svg>")

with open("docs/pipeline_flow_diagram.svg", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Saved docs/pipeline_flow_diagram.svg")
