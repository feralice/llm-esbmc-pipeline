# Handoff — sessão de 23-24 de agosto de 2026 (mineração, reestruturação e ligação ao pipeline do V2)

> Escrito por uma sessão do Claude Code rodando no repo `~/esbmc` (ferramenta), a pedido da
> Fernanda, pra dar contexto completo pra outra sessão do Claude rodando dentro de `llm_esbmc`.
> Não é memória automática, é resumo de trabalho de uma sessão longa. Ler isso antes de mexer em
> `dataset/v2_real_world/`, `research_pipeline/pipeline.py`, `src/main.py`, ou em
> `docs/GUIA_DATASET_PIPELINE.md`.

## Resumo em uma frase

O dataset V2 (`dataset/v2_real_world/`) foi de 7 itens pro estado final desta sessão: **105
bugs reais, todos genuinamente confirmados pelo ESBMC (0 pendência conhecida)**, reestruturado
de pasta-por-categoria pra pasta única + `detection/` separado com código real intocado, e ligado
direto ao `research_pipeline` existente (modo `hybrid` evoluído, sem script separado).

## Estrutura do dataset

```text
dataset/v2_real_world/
├── bugs/                    # 105 harnesses pro ESBMC (nondet_*, __ESBMC_assume, abstração quando precisa)
├── detection/                # 103 arquivos, código real intocado, puxado do commit de verdade
├── ground_truths.json        # 1 arquivo só (não mais por categoria), cada item com "categories": [lista]
├── manifest_pilot.json       # liga detection_file ↔ harness_file ↔ provenance ↔ oracle ↔ abstraction
├── candidates_phase1.json    # histórico de mineração/triagem (não é dataset final, é rascunho)
└── README.md                 # status/findings, atualizado a cada leva
```

(103 em `detection/`, não 105 — 2 itens duplicados/gêmeos apontam pro mesmo arquivo de detecção,
documentado no próprio manifesto com `duplicate_of`.)

**Por que dois arquivos por bug**: a Fernanda identificou (documento próprio,
`docs/GUIA_DATASET_PIPELINE.md`) que misturar detecção e confirmação num arquivo só causa
"vazamento de gabarito" — se a LLM recebe o mesmo arquivo que o ESBMC usa pra confirmar, o nome da
função (`buggy_X`), comentário e `assert` de comparação já entregam a resposta.

- `detection/<id>.py`: código real, **sem nenhuma edição**, puxado literalmente do arquivo/commit
  real do projeto. Neutralização de nome pro prompt da LLM é responsabilidade do
  `research_pipeline` no momento de montar o prompt, não do dataset.
- `bugs/<id>.py`: o harness pro ESBMC (`nondet_*`, `__ESBMC_assume`, `assert`, às vezes par
  função-buggy/função-corrigida).
- `manifest_pilot.json`: por item, `oracle.kind` classifica o gabarito: `native_property` (ESBMC
  pega sozinho), `original_assert` (assert que já existia no código real), `fixed_version_equivalence`
  (compara com a versão corrigida do commit).

## Categorias e contagem final

8 categorias antigas + `incorrect_result` (nova, resultado numérico errado sem crash, ex: `pi`
errado no próprio ESBMC) + `variable_misuse`. Reconte sempre direto do `ground_truths.json`:

```bash
python3 -c "
import json
from collections import Counter
d = json.load(open('dataset/v2_real_world/ground_truths.json'))
print('total:', len(d['items']))
print(Counter(c for i in d['items'] for c in i['categories']))
"
```

No fechamento desta sessão: 105 itens — `invalid_precondition` 36, `none_misuse` 27,
`assertion_violation` 19, `out_of_bounds` 13, `type_mismatch` 10, `division_by_zero` 3,
`incorrect_result` 3, `variable_misuse` 3, `integer_overflow` 1 (soma > 105 porque alguns itens
têm 2 categorias).

## Fontes, por nível de confiança (breakdown que a Fernanda pediu ver)

- **76 BugsInPy** (Widyasari et al., ESEC/FSE 2020) — acadêmico, revisado por pares. Praticamente
  esgotado pro critério de qualidade usado (pandas/keras deram rendimento baixíssimo).
- **15 GitHub com issue real linkado** — fixes fora dos 18 projetos do BugsInPy, só aceitos quando
  o commit referenciava um número de issue real (`#N`/`Fixes #`), não julgamento do agente sozinho.
- **3 histórico do próprio ESBMC** (`src/python-frontend/models/*.py`, categoria `incorrect_result`).
- **11 só julgamento do agente** (leitura de commit/diff sem terceiro confirmando) — marcar como
  confiança mais baixa se for citar número na dissertação.

**89 de 105 (85%) têm validação humana independente.**

**Fontes tentadas e descartadas** (não repetir): GHSA (zero hit nos CWEs relevantes, é tudo vuln de
app web), CVEfixes (59GB, inviável), SVEN (só 386 funções, quase todo C/C++), HaPy-Bug (baixado e
inspecionado por completo — 899MB — não-BugsInPy dele é 100% CVE-security, mesmo problema do GHSA).

## Erros de proveniência encontrados e corrigidos nesta sessão

1. **`buggy_commit` era o commit do próprio fix** em pelo menos 8+ casos — mensagem já dizia "Fix
   .../"Fixes #N". Corrigido usando o commit pai. Checável: `git log --oneline -1 <buggy_commit>`
   e comparar a mensagem contra padrão de fix antes de aceitar.
2. **Função errada extraída** em pelo menos 3 casos (`tqdm.__init__` em vez de
   `tqdm.format_meter`; `_Projection.multi_get` em vez de `_Projection.get_index`) — só pego
   comparando o comentário do harness contra o texto do arquivo extraído.
3. **Duplicata do mesmo bug real sob IDs diferentes** — 9+ casos ao longo da sessão, mesmo commit
   minerado 2x sem perceber sobreposição.

## Auditoria final: todos os 105 rodados de novo com ESBMC

Cada item foi re-verificado (`esbmc bugs/<id>.py --z3 ...`) confirmando que a propriedade que
falha bate com a categoria/`expected_type` declarado, não só "alguma coisa falhou". Resultado:
**102/105 limpos de cara**, 9 precisaram só de `--unwind`/`--timeout` maior anotado (não é erro),
e **3 vieram como falsa confirmação** (`av_real_06`, `av_real_14`, `vm_real_01`) — o
`VERIFICATION FAILED` original vinha de um artefato interno (`unwinding assertion` no modelo de
string do ESBMC, `src/c2goto/library/python/string.c`), não da propriedade real.

**Os 3 foram consertados** trocando `--unwind N --timeout 20s` por `--incremental-bmc` (sem bound
fixo, incrementa até achar ou provar). Os três batem na propriedade real agora:
`av_real_06` k=20, `av_real_14` k=21, `vm_real_01` k=2 (rápido!). **Dataset fecha 105/105
genuinamente confirmados, 0 pendência.**

**Achado importante pro pipeline**: isso não é bug do `research_pipeline` — `esbmc_runner.py` já
usa `--incremental-bmc` por padrão em toda função (`run_esbmc_direct` linha 40,
`run_esbmc_on_function` linha 190, `run_esbmc_function_baseline` linha 267). O problema só existiu
porque, na hora de MINERAR/construir o dataset, os agentes testaram cada harness na mão via bash
direto (`esbmc file.py --z3 --unwind 6`), fora do pipeline. Quando o pipeline real roda, já usa a
flag certa, sem precisar de ajuste nenhum.

## Ligação ao `research_pipeline` (evolução, não script novo)

A Fernanda pediu explicitamente: **nada de script separado**, evoluir o `hybrid` (Flow B) que já
existe. Feito:

- `research_pipeline/pipeline.py`: `run_pipeline_multi()` ganhou parâmetro opcional `harness_for:
  dict[str, Path] | None` — mapa `{caminho_absoluto_do_detection_file: caminho_do_harness}`. Quando
  o arquivo de entrada tem uma entrada nesse mapa, o finding verificável roda ESBMC no harness
  (`run_esbmc_direct`, arquivo inteiro, sem `--function`) em vez de `--function` no mesmo arquivo
  que a LLM leu. Sem a flag, `hybrid` continua idêntico ao comportamento do V1.
- `src/main.py`: flag nova `--v2-manifest <caminho>`, só usada no modo `hybrid`. Carrega
  `manifest_pilot.json` e monta o `harness_for` automaticamente (`_load_v2_harness_map`).
- `scripts/v2_pilot_detect.py` (protótipo que existiu por um tempo nesta sessão) **foi apagado**,
  junto com o `pilot_detect_report.json` que ele gerou.

Uso:
```bash
python src/main.py --mode hybrid --input dataset/v2_real_world/detection \
  --v2-manifest dataset/v2_real_world/manifest_pilot.json --model gpt-4o
```

Testado (sintaxe, import, parsing de args, carregamento dos 103 mapeamentos do manifesto) — **ainda
não rodado de ponta a ponta com nenhum modelo pago**. Único teste real até agora foi o protótipo
antigo (já apagado) com `qwen2.5-coder:7b` local: **0 de 72 detectados** — mas é modelo pequeno
(7B, grátis, local), não prova nada sobre o dataset/método em si, só sobre a capacidade desse
modelo específico. Falta testar com modelo maior (gpt-4o/claude) antes de tirar qualquer conclusão
sobre a Alternativa A (harness pronto no dataset) do `docs/GUIA_DATASET_PIPELINE.md` §13.1.

Classificação que sai desse fluxo: `esbmc_native_bug` quando o harness confirma (reaproveita
constante já existente em `models.py`, não foram criadas constantes novas) — semanticamente não é
um encaixe perfeito (o nome sugere "achado sem LLM"), mas é o que já existe e evita inventar
máquina de classificação nova só pro V2.

## O que falta / próximos passos

1. Rodar `hybrid --v2-manifest` com um modelo de verdade (gpt-4o ou claude) nos 105 casos e olhar
   o `report.json` — isso é o teste real da Alternativa A que ainda não aconteceu.
2. Modo `benchmark` (P/R/F1, MCC, bootstrap CI) ainda não está ligado ao formato do V2 — só
   funciona com a estrutura de ground truth do V1 hoje.
3. Decisões metodológicas ainda pendentes de orientador: ver `docs/GUIA_DATASET_PIPELINE.md`,
   seções "Decisões prioritárias" (§11.9, §17.5, §19.1, §23.1, §24.2) e §25.

## Outros achados relevantes (fora do dataset, vale registrar/reportar depois)

Bugs reais e vivos no próprio ESBMC (não histórico, atuais, nenhum virou item de dataset):
`dict.update()` não sobrescrevendo chave existente; custo anômalo de VCC (17227 VCCs pra dict de 2
chaves); crash do frontend (`irep2_cast_error`) num `for ... del d[f]`; crash de encoding Z3 em
`int.from_bytes`; e o próprio achado desta sessão sobre `__python_str_concat`
(`src/c2goto/library/python/string.c:1363`) travar em `unwinding assertion` mesmo com string
**concreta** (não seria necessário nenhum laço simbólico) — vale investigar se o modelo de string
otimiza pra literais conhecidos em tempo de verificação, provavelmente não.
