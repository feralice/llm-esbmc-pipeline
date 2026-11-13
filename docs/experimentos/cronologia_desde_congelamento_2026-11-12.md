# Cronologia desde o congelamento 11d (11 a 12/11/2026)

Registro único, em ordem cronológica, do que aconteceu depois da tag `v2-congelado-2026-11d`. Cada entrada diz
o que foi feito, com qual código e onde está a saída. Os scans de repositórios reais estão detalhados em
`indice_scans_2026-11-12.md`. A tag não é rodada oficial de resultado: há decisões pendentes listadas no fim.

## 1. Congelamento 11d

- Tag: `v2-congelado-2026-11d`, no commit `63c9e42` (branch `master`, na época).
- Suíte no congelamento: 1846 aprovados, 1 pulado.
- ESBMC: 8.6.0 (commit `b1b4d6ccf9` do `~/esbmc-master`).
- Pendências registradas na própria tag: prompt A2 editado depois do 11c, escalonamento de timeout em
  `verify/esbmc_run.py`, e parse de Ollama que agora levanta erro em vez de devolver lista vazia.

## 2. Rodada dos 47 casos PGENE601 (11/11, código `63c9e42`)

- Pasta: `artifacts/pgene601/rodada-2026-11-11/`. Script: `run.sh` copiado da rodada de 09/11, com só a pasta de saída trocada.
- Argumentos: `--mode hybrid --v2-stage end-to-end`, variantes A1 e A2, Claude Sonnet 5.5 pela assinatura, self-healing padrão, bound 5, timeout 180.
- Tentativas:
  1. 11/11, 20h28: saiu com código 2 (erro de rede `EAI_AGAIN` em `FramerTLS.decode`).
  2. 12/11, 01h24: saiu com código 3 (limite de cota).
  3. 12/11, 04h01: concluída (código 0).
- Resultado (comparado com a rodada de 08/11, que é a que o `run.sh` usa):

| Métrica | 08/11 | 11/11 |
|---|---:|---:|
| Hipóteses | 119 | 116 |
| Bugs confirmados pela expressão | 9 | 9 |
| Bugs confirmados pela função | 14 | 15 |
| Bugs com hipótese certa | 36 | 37 |
| Vereditos `CONFIRMED` | 17 | 15 |

- Leitura: resultado parecido. A queda de `CONFIRMED` vem de hipóteses que não se repetem entre rodadas (o LLM
  gera suspeitas diferentes). Nas 84 hipóteses pareadas com a rodada de 09/11, `CONFIRMED` foi de 12 para 13.
- Custo (telemetria corrigida, primeira medição real): 1109 chamadas (1055 de síntese, 54 de detecção).
  Custo equivalente informado pelo CLI: cerca de US$ 145 (síntese 137, detecção 8). Cobrado por token: 0,
  porque é assinatura. Entrada total: cerca de 47 milhões de tokens, com 32 milhões de escrita de cache e
  12 milhões de leitura na síntese.
- Ressalvas: o prompt A2 e o timeout usados são os atuais, não os do congelamento. Esta rodada não é a oficial.
- Saídas: `resumo.md`, `funil.txt`, `tabela.md`, `llm_telemetry.json`, `v2_verify_report.json`.

## 3. Mudanças de código depois do congelamento

Todas estão em `master` e foram publicadas no `origin` em 12/11 (`origin/master` foi de `7917192` para `44ce2a8`).

| Commit | O que muda | Efeito nos resultados |
|---|---|---|
| `ce678dd` | Telemetria preservada quando o limite de uso estoura durante a revisão | só registro de custo |
| `ad477cd` | `--workers` (paralelismo), `--detection-cache`, `--heal-triage` (opcional), regra `IOError` para `OSError` | padrão desligado, exceto a regra `IOError` (que só entra se a sonda mostrar que o ESBMC não define o nome) |
| `d73bc12` | Gate de replay recusa travessia por `str.format`; telemetria registra tentativas HTTP | pode recusar harness com `format` de atributo (efeito conservador) |
| `079ecfa` | Merge de `master` em `feat/workers` | nenhum |
| `da13a4d` | CLI `llm-esbmc scan` e extensão `/verify-repo` com `backend=codex` | só interface |
| `44ce2a8` | Merge de `feat/workers` em `master` | ver acima |

Também entrou em `master` o commit da outra sessão `7ab6230` (contexto de repositório no scan), que não revisei.

Mudanças fora de `master`, ainda sem commit:
- `--resume` na CLI (`src/research_pipeline/cli.py`) e `scripts/scan_com_retomada.sh`.
- Branch `fix/caller-exception-context` (worktree `~/mestrado/llm_esbmc-caller`): análise de `try/except` dos
  chamadores, veredito `HANDLED_BY_CALLER`, rótulos do relatório, módulo `llm/exception_context.py` e a variante
  A21 (ainda não funciona com o prompt padrão, porque a âncora não existe nesse caminho).
- `docs/projeto/tabela_roteamento_prompts_v1.md`: tabela proposta, não implementada.
- Rascunho de issue: `docs/projeto/rascunho_issue_gsa_17_campos_2026-11-12.md` (já publicada, ver abaixo).

## 4. Scans em repositórios reais (12/11)

Detalhes e status em `indice_scans_2026-11-12.md`. Resumo:

- **Issue aberta:** `adafruit/Adafruit_CircuitPython_GPS#132` (GSA de 17 campos perde o 12º satélite). Achado do LLM,
  confirmado à mão com o driver real.
- **Bug já reportado:** pynmea2, `IndexError` em sentença proprietária truncada. Já é a PR #189 do repo. Nada publicado.
- **Falsos positivos:** os `CONFIRMED` do GPS (capturados em `_parse_data`) e os da SAM (API Gateway envia `httpMethod`).
- **Fora do contrato documentado:** os `CONFIRMED` do secrets rotation (segredo binário e item não-texto em `permissions`).
- **Infraestrutura:** falhas do Codex no Glue (timeout e roteamento). Nenhum veredito sobre o código.
- **Em andamento na hora deste registro:** pynmea2, pyserial completo e as filas de 30 funções. Ver o índice.

## 5. Problemas conhecidos

- `relatorio.md` do secrets rotation está desatualizado (mostra falha de 40 de 40 do Codex). Não citar.
- O `gh` está autenticado como `feralice`, mas o repo de secrets restringe criação de issue. A nota anterior sobre
  token inválido estava errada.
- Nota de issue sobre o pynmea2 não foi publicada: a PR #189 já cobre o caso.

## 6. Decisões pendentes

1. Prompt A2: restaurar o texto congelado e colocar a versão nova em outra variante (A2b), ou manter a edição?
2. Escalonamento de timeout em `esbmc_run.py`: atrás de flag, ou rodar o conjunto congelado e reportar a diferença?
3. Parse de Ollama: intencional? Registrar.
4. A rodada de 11/11 vira resultado oficial, ou fica como experimento?
5. Comentar na PR #189 com os casos ASH e TNL (ação pública).
6. Tabela de roteamento de prompts: aprovar as quatro decisões levantadas (ordem de prioridade, união ou escolha,
   entrada da A21, padrão).

## 7. Próximos passos

- Concluir as filas (paho-mqtt, pyserial, cantools, pymodbus, gpiozero, python-can, bleak, pyvisa) e o pyserial completo,
  registrando cada um no índice.
- Refazer o relatório do secrets rotation a partir do checkpoint.
- Investigar a falha de roteamento do Codex antes de repetir o Glue.
- Commitar, quando você pedir: `--resume`, o script de retomada e este registro.
