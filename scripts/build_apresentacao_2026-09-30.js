const pptxgen = require("pptxgenjs");

const C = { bg: "FAFAFA", ink: "1F2937", muted: "6B7280", teal: "0F766E", tealSoft: "E6F2F1",
            amber: "B45309", amberSoft: "FDF1E3", line: "D1D5DB", white: "FFFFFF", dark: "12302D" };
const HEAD = "Cambria", BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "Pipeline híbrido LLM + ESBMC-Python";

function base(title, opts = {}) {
  const s = pres.addSlide();
  s.background = { color: opts.dark ? C.dark : C.bg };
  if (title) {
    s.addText(title, { x: 0.5, y: 0.3, w: 9.0, h: 0.85, fontFace: HEAD, fontSize: 24, bold: true,
      color: opts.dark ? C.white : C.ink, valign: "top", margin: 0, isTextBox: true });
  }
  return s;
}

function bullets(s, items, box) {
  s.addText(items.map((t, i) => {
    const runs = Array.isArray(t) ? t : [{ text: t }];
    return runs.map((r, j) => ({ text: r.text, options: { bold: !!r.bold, color: r.color || C.ink,
      bullet: j === 0 ? { indent: 14 } : false, breakLine: j === runs.length - 1 && i < items.length - 1,
      paraSpaceAfter: 6 } }));
  }).flat(), { x: box.x, y: box.y, w: box.w, h: box.h, fontFace: BODY, fontSize: box.size || 14,
    color: C.ink, valign: "top", margin: 0, isTextBox: true });
}

function card(s, x, y, w, h, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08,
    fill: { color: fill || C.white }, line: { color: C.line, width: 0.75 } });
}

function table(s, rows, box, colW, header = true) {
  const data = rows.map((r, i) => r.map(cell => ({ text: String(cell), options: {
    bold: header && i === 0, color: header && i === 0 ? C.white : C.ink,
    fill: { color: header && i === 0 ? C.teal : (i % 2 ? C.white : "F3F4F6") } } })));
  s.addTable(data, { x: box.x, y: box.y, w: box.w, colW, fontFace: BODY, fontSize: box.size || 11,
    border: { type: "solid", pt: 0.5, color: C.line }, valign: "middle", margin: 0.05, autoPage: false });
}

// 1. Title
{
  const s = base(null, { dark: true });
  s.addText("Pipeline híbrido LLM + ESBMC-Python", { x: 0.7, y: 1.55, w: 8.6, h: 0.9, fontFace: HEAD,
    fontSize: 34, bold: true, color: C.white, margin: 0, isTextBox: true });
  s.addText("Redesenho da verificação: hipóteses congeladas, harness determinístico e validação por execução",
    { x: 0.7, y: 2.5, w: 8.2, h: 0.8, fontFace: BODY, fontSize: 17, color: "CFE7E4", margin: 0, isTextBox: true });
  s.addText("Fernanda · PPGINF · orientação: Lucas Cordeiro · 30/09/2026", { x: 0.7, y: 4.45, w: 8.6, h: 0.4,
    fontFace: BODY, fontSize: 12, color: "9FC7C2", margin: 0, isTextBox: true });
}

// 2. Central message
{
  const s = base("A LLM acha o bug; o gargalo estava em transformar a hipótese em verificação");
  bullets(s, [
    [{ text: "Diagnóstico: ", bold: true }, { text: "o pipeline antigo confirmava quase nada no código real." }],
    [{ text: "Nova arquitetura: ", bold: true }, { text: "a LLM não escreve mais código de verificação." }],
    [{ text: "Harness genérico: ", bold: true }, { text: "substitutos automáticos para bibliotecas, objetos e tipos que o ESBMC não modela." }],
    [{ text: "Validação por execução: ", bold: true }, { text: "falsos positivos e falsos negativos do ESBMC-Python 8.5 medidos e separados." }],
    [{ text: "Resultados: ", bold: true }, { text: "função com bug localizada em 97% dos casos e primeiras confirmações no código original." }],
  ], { x: 0.5, y: 1.35, w: 5.4, h: 3.8, size: 15 });
  card(s, 6.3, 1.35, 3.2, 3.6, C.tealSoft);
  s.addText([{ text: "97%", options: { fontSize: 54, bold: true, color: C.teal, breakLine: true } },
             { text: "das funções com bug localizadas pela LLM (101 de 104)", options: { fontSize: 14, color: C.ink } }],
    { x: 6.55, y: 1.7, w: 2.7, h: 2.9, fontFace: HEAD, valign: "middle", margin: 0, isTextBox: true });
}

// 3. Diagnosis
{
  const s = base("A versão anterior confirmava a abstração, não o código real");
  const stats = [["25 × 2", "hipóteses \"confirmadas\" só na abstração escalar contra 2 no código real"],
                 ["22 de 34", "resultados inconclusivos sem motivo registrado"],
                 ["763", "chamadas de síntese para 135 hipóteses, em seis estratégias em cascata"]];
  stats.forEach(([n, t], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.4, 2.85, 2.3);
    s.addText(n, { x: x + 0.2, y: 1.6, w: 2.45, h: 0.8, fontFace: HEAD, fontSize: 32, bold: true,
      color: C.amber, margin: 0, isTextBox: true });
    s.addText(t, { x: x + 0.2, y: 2.45, w: 2.45, h: 1.1, fontFace: BODY, fontSize: 13, color: C.ink,
      valign: "top", margin: 0, isTextBox: true });
  });
  s.addText("Rodada de referência de 27/09 (gpt-4o-mini, 135 hipóteses). Conclusão: o problema estava na arquitetura da síntese, não apenas no modelo.",
    { x: 0.5, y: 4.0, w: 9.0, h: 0.8, fontFace: BODY, fontSize: 14, color: C.muted, margin: 0, isTextBox: true });
}

// 4. Example
{
  const s = base("Exemplo: uma hipótese falsa virou \"confirmação\" (ip_real_15, black)");
  card(s, 0.5, 1.35, 4.4, 1.55, "F3F4F6");
  s.addText("while self.previous_defs and self.previous_defs[-1] >= depth:\n    self.previous_defs.pop()",
    { x: 0.65, y: 1.5, w: 4.1, h: 1.25, fontFace: "Courier New", fontSize: 11, color: C.ink, valign: "middle", margin: 0, isTextBox: true });
  s.addText("Código real", { x: 0.5, y: 3.0, w: 4.4, h: 0.3, fontFace: BODY, fontSize: 11, color: C.muted, margin: 0, isTextBox: true });
  bullets(s, [
    [{ text: "Hipótese da LLM: ", bold: true }, { text: "pop() em lista vazia. É falsa: o while já impede." }],
    [{ text: "Harness gerado: ", bold: true }, { text: "trocou a lista por um inteiro, removeu o while e verificou previous_defs >= 0." }],
    [{ text: "Resultado: ", bold: true }, { text: "o ESBMC achou contraexemplo e o caso contou como confirmado na abstração." }],
  ], { x: 5.2, y: 1.35, w: 4.3, h: 3.6, size: 14 });
}

// 5. Architecture
{
  const s = base("Nova arquitetura: a LLM propõe, o programa monta, ESBMC e execução decidem juntos");
  const steps = ["Código real", "LLM aponta o bug", "AST confere", "Harness por código", "ESBMC", "Execução no CPython"];
  steps.forEach((t, i) => {
    const x = 0.5 + i * 1.53;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.4, w: 1.33, h: 0.85, rectRadius: 0.08,
      fill: { color: i === 3 ? C.teal : C.white }, line: { color: C.teal, width: 1 } });
    s.addText(t, { x, y: 1.4, w: 1.33, h: 0.85, fontFace: BODY, fontSize: 12, bold: true, align: "center",
      valign: "middle", color: i === 3 ? C.white : C.teal, margin: 0.03, isTextBox: true });
    if (i < steps.length - 1) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 1.36, y: 1.72, w: 0.14, h: 0.2,
      fill: { color: C.muted }, line: { color: C.muted, width: 0 } });
  });
  bullets(s, [
    [{ text: "Hipótese congelada: ", bold: true }, { text: "localização e expressão suspeita não mudam entre tentativas." }],
    [{ text: "Código original preservado: ", bold: true }, { text: "a função analisada entra sem alteração lógica." }],
    [{ text: "Harness determinístico: ", bold: true }, { text: "montado pelo programa, nunca escrito pela LLM." }],
    [{ text: "Reparo limitado: ", bold: true }, { text: "no máximo duas correções, guiadas pelo erro do ESBMC." }],
    [{ text: "Sem repetição de resultado seguro: ", bold: true }, { text: "repetir até achar violação seria forçar a confirmação." }],
  ], { x: 0.5, y: 2.6, w: 9.0, h: 2.6, size: 14 });
}

// 6. LLM output
{
  const s = base("A LLM agora descreve só as entradas, em JSON");
  card(s, 0.5, 1.35, 4.2, 2.6, "F3F4F6");
  s.addText('{\n  "params": {"depth": "int"},\n  "attributes": {"previous_defs": "list[int]"},\n  "stubs": {"to_bytes": "str"},\n  "assumptions": []\n}',
    { x: 0.65, y: 1.5, w: 3.95, h: 2.3, fontFace: "Courier New", fontSize: 11, color: C.ink, valign: "middle", margin: 0, isTextBox: true });
  bullets(s, [
    "Tipos aceitos: inteiros, reais, booleanos, texto, bytes, listas e dicionários aninhados, tuplas, valores opcionais e objetos com campos.",
    "Pré-condições só podem usar as entradas e len().",
    "Tipo real não representável é limite do método, não erro da LLM.",
    "A categoria do bug virou metadado: não participa da geração nem da confirmação.",
  ], { x: 5.0, y: 1.35, w: 4.5, h: 3.7, size: 14 });
}

// 7. Libraries
{
  const s = base("Bibliotecas que o ESBMC não abre viram substitutos gerados pelo programa");
  table(s, [
    ["Uso no código", "Substituto", "Tipo"],
    ["chamada de função ou método", "função que devolve valor não determinístico", "informado pela LLM"],
    ["constante da biblioteca", "valor não determinístico", "informado pela LLM"],
    ["classe base, anotação, isinstance", "classe vazia", "não precisa"],
    ["exceção levantada ou capturada", "subclasse de Exception", "não precisa"],
    ["cadeia email.utils.parsedate_tz(...)", "referência renomeada para email_utils", "informado pela LLM"],
    ["classe instanciada e usada como tipo", "classe com construtor vazio", "não precisa"],
  ], { x: 0.5, y: 1.35, w: 9.0, size: 11.5 }, [3.2, 3.6, 2.2]);
  s.addText("Na primeira execução real, 53 de 86 casos paravam na importação. Uma confirmação que depende de substituto vale se a biblioteca puder devolver aquele valor.",
    { x: 0.5, y: 4.45, w: 9.0, h: 0.7, fontFace: BODY, fontSize: 12.5, color: C.muted, margin: 0, isTextBox: true });
}

// 8. ESBMC findings
{
  const s = base("O veredito do ESBMC-Python 8.5 sozinho não basta em nenhum dos dois sentidos");
  table(s, [
    ["Programa", "Execução real", "ESBMC-Python 8.5"],
    ["while defs and defs[-1] >= d: defs.pop()", "seguro", "aponta IndexError (falso positivo)"],
    ["v: Optional[int] = None; v + 1", "TypeError", "não detecta (falso negativo)"],
    ["exceção não tratada", "linha exata", "reportada na linha 0"],
  ], { x: 0.5, y: 1.35, w: 9.0, size: 12 }, [4.0, 1.8, 3.2]);
  card(s, 0.5, 3.3, 9.0, 1.6, C.tealSoft);
  s.addText([{ text: "Consequência: ", options: { bold: true, color: C.teal } },
             { text: "a confirmação exige que o ESBMC aponte a violação e que a execução concreta do mesmo programa reproduza a mesma exceção na linha da hipótese (validação por execução, Beyer et al., TAP 2018)." }],
    { x: 0.75, y: 3.45, w: 8.5, h: 1.3, fontFace: BODY, fontSize: 14, color: C.ink, valign: "middle", margin: 0, isTextBox: true });
}

// 9. Verdicts
{
  const s = base("Os vereditos separam erro da LLM, limite do método e limite do verificador");
  table(s, [
    ["Veredito", "Significado"],
    ["Confirmado", "ESBMC e execução concordam na exceção e na linha da hipótese"],
    ["Falso negativo do ESBMC", "a execução reproduz o bug, o ESBMC não detecta"],
    ["Não validado", "o ESBMC aponta violação que a execução não reproduz"],
    ["Outra falha", "a execução quebra em outra linha"],
    ["Não confirmado", "nenhum dos dois encontra o bug"],
    ["Não suportado / dependência ausente", "limite do método ou do dataset"],
    ["Especificação falhou", "a LLM não produziu uma descrição válida"],
  ], { x: 0.5, y: 1.35, w: 9.0, size: 12 }, [3.0, 6.0]);
  s.addText("Só o primeiro conta como confirmação do bug real.", { x: 0.5, y: 4.7, w: 9.0, h: 0.4,
    fontFace: BODY, fontSize: 13, bold: true, color: C.teal, margin: 0, isTextBox: true });
}

// 10. Answers
{
  const s = base("Respostas às dúvidas de 23/09");
  bullets(s, [
    [{ text: "Bug do ESBMC com None: ", bold: true }, { text: "confirmado de forma independente; Optional[int] somado a inteiro não é detectado no 8.5 e agora é medido como falso negativo." }],
    [{ text: "Harness escalar como evidência: ", bold: true }, { text: "removido. Não conta mais como confirmação." }],
    [{ text: "Executar a função real: ", bold: true }, { text: "adotado como validação obrigatória depois do ESBMC." }],
    [{ text: "Duas categorias possíveis: ", bold: true }, { text: "a detecção passa a ser medida por localização; a categoria vira análise secundária." }],
    [{ text: "Pytest gerado pelo ESBMC: ", bold: true }, { text: "substituído pela reexecução própria, que também valida a linha e o tipo da exceção." }],
  ], { x: 0.5, y: 1.3, w: 9.0, h: 3.9, size: 14.5 });
}

// 11. Coverage
{
  const s = base("Cada versão do harness levou mais bugs reais até o verificador");
  s.addChart(pres.charts.BAR, [{ name: "Aptos à verificação", labels: ["tipos simples", "+ stubs", "+ objetos e tipos", "+ métodos e cadeias"], values: [64, 70, 72, 82] }],
    { x: 0.5, y: 1.3, w: 5.6, h: 3.8, barDir: "col", chartColors: [C.teal], showValue: true, dataLabelPosition: "outEnd",
      dataLabelColor: C.ink, dataLabelFontSize: 12, catAxisLabelColor: C.muted, valAxisLabelColor: C.muted,
      valAxisMinVal: 0, valAxisMaxVal: 116, valGridLine: { color: "E5E7EB", size: 0.5 }, catGridLine: { style: "none" },
      showLegend: false, showTitle: true, title: "Casos aptos, de 116 (sem LLM)", titleFontSize: 12, titleColor: C.ink });
  bullets(s, [
    [{ text: "15 ", bold: true }, { text: "com dependência ausente, em sua maioria casos sem o arquivo-fonte completo" }],
    [{ text: "15 ", bold: true }, { text: "com construções fora do alcance do verificador (async, recorte que alteraria dados globais, decoradores externos)" }],
    [{ text: "4 ", bold: true }, { text: "com localização inválida" }],
  ], { x: 6.4, y: 1.5, w: 3.1, h: 3.6, size: 13 });
}

// 12. RQ1
{
  const s = base("RQ1: a LLM acha a função com bug quase sempre, mas acerta a categoria em metade");
  s.addChart(pres.charts.BAR, [{ name: "Revocação", labels: ["arquivo", "função", "categoria no arquivo", "categoria, dada a função", "expressão exata"], values: [98, 97, 49, 47, 20] }],
    { x: 0.5, y: 1.3, w: 5.7, h: 3.8, barDir: "bar", chartColors: [C.teal], showValue: true, dataLabelPosition: "outEnd",
      dataLabelFormatCode: '0"%"', dataLabelColor: C.ink, dataLabelFontSize: 12, catAxisLabelColor: C.ink, catAxisLabelFontSize: 11,
      valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 110, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      catAxisOrientation: "maxMin", showLegend: false, showTitle: true, title: "Acerto por critério (104 bugs, gpt-4o-mini)", titleFontSize: 12, titleColor: C.ink });
  bullets(s, [
    "Função com bug: 101 de 104, precisão 86%.",
    "Categoria certa: 51 de 104 (precisão 30%).",
    "Trecho exato: 21 de 104.",
    "Medir só pela categoria subestimava a localização; por isso ela deixou de guiar a verificação.",
  ], { x: 6.5, y: 1.5, w: 3.0, h: 3.6, size: 13 });
}

// 13. RQ2 / RQ3
{
  const s = base("RQ2 e RQ3: as primeiras confirmações formais no código original");
  table(s, [
    ["", "RQ2 (localização dada)", "RQ3 (ponta a ponta)"],
    ["hipóteses", "125", "138"],
    ["chegaram à especificação", "91", "79"],
    ["confirmadas no código original", "3", "1 (condicional)"],
    ["falso negativo do ESBMC", "0", "1"],
    ["não confirmadas / não validadas", "6 / 2", "4 / 0"],
    ["paradas por limite do ESBMC ou do harness", "63", "60"],
    ["dependência ausente / especificação inválida", "26 / 14", "21 / 21"],
  ], { x: 0.5, y: 1.3, w: 5.9, size: 11 }, [2.9, 1.5, 1.5]);
  card(s, 6.7, 1.3, 2.8, 3.85, C.amberSoft);
  s.addText([{ text: "Confirmações", options: { bold: true, color: C.amber, fontSize: 14, breakLine: true } },
             { text: "cli_bool_option (youtube-dl): AssertionError no assert do próprio código.", options: { fontSize: 11.5, breakLine: true } },
             { text: " ", options: { fontSize: 5, breakLine: true } },
             { text: "match (thefuck): IndexError em split()[1] com comando de uma palavra.", options: { fontSize: 11.5, breakLine: true } },
             { text: " ", options: { fontSize: 5, breakLine: true } },
             { text: "WebSocketHandler.set_nodelay (tornado): condicional ao estado do objeto; é a da ponta a ponta.", options: { fontSize: 11.5 } }],
    { x: 6.9, y: 1.45, w: 2.45, h: 3.6, fontFace: BODY, color: C.ink, valign: "top", margin: 0, isTextBox: true });
  s.addText("Gargalo: o alcance do ESBMC-Python sobre código real, não a LLM.",
    { x: 0.5, y: 4.75, w: 5.9, h: 0.4, fontFace: BODY, fontSize: 11.5, color: C.muted, margin: 0, isTextBox: true });
}

// 14. Control experiments
{
  const s = base("Com o mesmo custo, o erro do ESBMC quase triplica a taxa de verificação");
  s.addChart(pres.charts.BAR, [
      { name: "Reparo guiado", labels: ["1 chamada", "2 chamadas", "3 chamadas"], values: [3.3, 8.8, 12.1] },
      { name: "Amostragem independente", labels: ["1 chamada", "2 chamadas", "3 chamadas"], values: [3.3, 4.4, 4.4] }],
    { x: 0.5, y: 1.3, w: 5.4, h: 3.5, barDir: "col", barGrouping: "clustered", chartColors: [C.teal, "9CA3AF"],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelFontSize: 11, dataLabelColor: C.ink,
      catAxisLabelColor: C.ink, valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 15, valGridLine: { style: "none" },
      catGridLine: { style: "none" }, showLegend: true, legendPos: "b", legendFontSize: 11,
      showTitle: true, title: "Hipóteses com veredito do ESBMC (RQ2, 125 hipóteses, mesmo orçamento)", titleFontSize: 11, titleColor: C.ink });
  bullets(s, [
    [{ text: "Reparo: ", bold: true }, { text: "3 confirmados e 14 especificações inválidas, contra 2 e 35 na amostragem; 346 mil e 354 mil tokens." }],
    [{ text: "Confirmação falsa: ", bold: true }, { text: "nenhuma nas 107 versões corrigidas. Em cli_bool_option corrigido o ESBMC ainda acusa violação, mas a execução não reproduz: fica não validado." }],
    [{ text: "Ressalva: ", bold: true }, { text: "uma rodada por braço; repetir para medir a variação." }],
  ], { x: 6.2, y: 1.35, w: 3.3, h: 3.8, size: 12.5 });
  s.addNotes("Comparação com amostragem de mesmo custo segue Olausson et al. (ICLR 2024).");
}

// 14. ESBMC limits
{
  const s = base("Dez limites do ESBMC-Python documentados com reprodutores mínimos");
  const groups = [["Falsos positivos", "remoção protegida por verificação de lista vazia; método de classe aninhada não resolvido"],
                  ["Falsos negativos", "soma com valor opcional nulo; atributo de texto opcional (PR #8014)"],
                  ["Falhas do verificador", "falha de segmentação com expressão condicional; exceção sem linha (corrigido na PR #8014); FAILED e UNKNOWN na mesma execução"],
                  ["Construções recusadas", "async, fatiamento 2-D do numpy, chamada com *args, formatação com %"]];
  groups.forEach(([h, t], i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.85;
    card(s, x, y, 4.4, 1.7);
    s.addText(h, { x: x + 0.2, y: y + 0.15, w: 4.0, h: 0.4, fontFace: HEAD, fontSize: 15, bold: true, color: C.teal, margin: 0, isTextBox: true });
    s.addText(t, { x: x + 0.2, y: y + 0.6, w: 4.0, h: 1.0, fontFace: BODY, fontSize: 12.5, color: C.ink, valign: "top", margin: 0, isTextBox: true });
  });
  s.addText("Comparação entre a versão 8.5.0 e a PR #8014; cada limite tem o caso do dataset onde apareceu.",
    { x: 0.5, y: 5.0, w: 9.0, h: 0.35, fontFace: BODY, fontSize: 11, color: C.muted, margin: 0, isTextBox: true });
}

// 15. Agent arm
{
  const s = base("Braço experimental: quanto um agente interativo recupera além do método automático?");
  bullets(s, [
    "Para os casos que o harness automático não alcança, um agente (Claude Code com o plugin ESBMC) tenta construir o harness de forma interativa.",
    "O pipeline não confia no agente: roda o ESBMC por conta própria, reexecuta no CPython e aplica a mesma regra de confirmação.",
    "Se o agente alterar o corpo da função analisada, o resultado fica fora da contagem principal.",
  ], { x: 0.5, y: 1.35, w: 9.0, h: 3.6, size: 15 });
}

// 16. Literature
{
  const s = base("Literatura que fundamenta as decisões");
  table(s, [
    ["Trabalho", "Decisão que sustenta"],
    ["Beyer et al. (TAP 2018)", "validar contraexemplos executando o programa"],
    ["Clarke et al. (CAV 2000)", "contraexemplos espúrios em abstrações"],
    ["Olausson et al. (ICLR 2024)", "reparo guiado comparado com amostragem de mesmo custo"],
    ["Zhang et al. (ISSTA 2024)", "drivers gerados por LLM falham em APIs complexas"],
    ["Amusuo et al. (arXiv 2025)", "drivers gerados produzem falhas espúrias por estado irreal"],
    ["Wu, Barrett e Narodytska (ICLR 2024)", "a LLM propõe, o verificador decide"],
  ], { x: 0.5, y: 1.35, w: 9.0, size: 12 }, [3.4, 5.6]);
}

// 17. Next steps
{
  const s = base("Próximos passos e decisões", { dark: true });
  s.addText("Prioridade alta", { x: 0.5, y: 1.3, w: 4.3, h: 0.4, fontFace: HEAD, fontSize: 16, bold: true, color: "CFE7E4", margin: 0, isTextBox: true });
  s.addText([
    { text: "Concluir reparo × amostragem e versões corrigidas", options: { bullet: { indent: 14 }, breakLine: true } },
    { text: "Rodar o agente nos casos restantes", options: { bullet: { indent: 14 }, breakLine: true } },
    { text: "Revisar e integrar 199 bugs validados do BugsInPy", options: { bullet: { indent: 14 }, breakLine: true } },
    { text: "Avaliar um modelo mais forte na especificação", options: { bullet: { indent: 14 } } },
  ], { x: 0.5, y: 1.8, w: 4.3, h: 3.2, fontFace: BODY, fontSize: 14, color: C.white, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
  s.addText("Para discutir", { x: 5.2, y: 1.3, w: 4.3, h: 0.4, fontFace: HEAD, fontSize: 16, bold: true, color: "F6C68B", margin: 0, isTextBox: true });
  s.addText([
    { text: "Usar a localização do gabarito como entrada controlada na RQ2?", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Abrir issues no ESBMC-Python com os dez reprodutores?", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Confirmações com substituto de biblioteca entram na métrica principal?", options: { bullet: { type: "number" } } },
  ], { x: 5.2, y: 1.8, w: 4.3, h: 3.2, fontFace: BODY, fontSize: 14, color: C.white, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
}

pres.writeFile({ fileName: "apresentacao_2026-09-30.pptx" }).then(f => console.log("ok", f));
