# Lote A de melhorias do pipeline (04/11/2026)

Feito por um agente de IA (Claude) a pedido da Fernanda, numa cópia isolada do repositório (worktree),
sem commit. Nenhuma chamada a LLM paga foi feita: todos os testes usam LLM falsa. Itens 23, 24, 25 e 13
do plano.

## Item 23: parar a rodada quando o limite de uso da LLM acaba

**Problema.** Na rodada de 03/11, quando o limite de 5 horas da assinatura do Claude acabou, cada
hipótese restante virou `PIPELINE_ERROR` (103 casos). O `claude -p` sai com código 1 e o motivo fica
no JSON da saída padrão, com a saída de erro vazia; por isso a mensagem gravada era só
"claude -p saiu com código 1: ". O piloto do item 14 (31/10) se perdeu do mesmo jeito.

**O que mudou.**

- Novo erro `UsageLimitReached` em `src/research_pipeline/llm/rate_limit.py`. Ele é levantado quando a
  mensagem de falha fala em limite de uso. Os textos reconhecidos vieram das rodadas gravadas em
  `artifacts/`: "You've hit your 5-hour limit · resets 1:30am" (Claude Code), "You’ve hit your usage
  limit" (Codex), "Claude usage limit reached", e também "credit balance is too low" e
  "insufficient_quota" das APIs.
- `claude -p` (detecção e especificação): o motivo agora é lido do JSON da saída padrão
  (`cli_failure_detail`, mesmo texto que já estava na cópia principal do repositório, para a junção
  não dar conflito).
- Codex (`turn.failed`), OpenAI e Gemini (cota diária), Anthropic API: 429 ou 529 que continua depois
  das 3 tentativas vira `UsageLimitReached`; um 400 comum continua erro normal.
- Sessão do agente (Claude Code) que termina com "You've hit your ... limit": antes virava
  `PIPELINE_ERROR`; agora para a rodada. Também vale para a segunda tentativa do agente (retry).
- Os laços que antes engoliam o erro agora deixam ele passar: `run_verify` (motor),
  `agent_verifier` (scan com agente), `run_agent_fallback` (nível 2), `api_agent`, `orchestrate`,
  filtro de smells, `judge_smells` e a detecção do scan. Outros erros continuam virando
  `PIPELINE_ERROR` como antes.
- `src/main.py`: na detecção do modo hybrid, o laço para na primeira função que bate no limite, grava
  o relatório parcial e o checkpoint (`interruption_reason: "usage_limit"`). No verify e no nível 2, o
  checkpoint fica com `status: "interrupted"` e `interruption_reason: "usage_limit"`. No scan, o
  checkpoint já é salvo a cada função e a cada hipótese. Nos três casos a saída é o código **3** com a
  mensagem "Limite de uso da LLM atingido ... retome com --resume depois que o limite renovar". O código
  2 continua sendo interrupção pelo teclado ou detecção parcial.
- Scripts `v2_agent_arm.py`, `v2_orchestrate.py` e `v2_judge.py`: saem com código 3 e mensagem, sem
  traceback. Eles já salvam cada caso terminado, então rodar de novo retoma.

**Testes.** `tests/test_usage_limit.py` (31 testes): mensagens reais reconhecidas e falhas comuns não
reconhecidas; `claude -p`, Codex e Anthropic levantam o erro; cada laço para no limite e guarda só o
que terminou; `main` sai com 3 e grava o checkpoint na detecção, no verify e no scan. Em
`tests/test_claude_cli_backend.py` entraram os dois testes de `cli_failure_detail` que já existiam na
cópia principal. O teste antigo `test_a_usage_limit_from_the_agent_session_is_a_pipeline_error`
virou `..._stops_the_run`, porque o comportamento mudou de propósito.

**Mutação.** Tirar cada um dos 8 `except UsageLimitReached: raise` faz um teste falhar (8 de 8).
Trocar o `break` da detecção por `continue`, ou tirar `UsageLimitReached` do `except` do verify,
também faz um teste falhar.

**Fora do item.** `scripts/v2_replay_specs.py` ficou como estava: ele só grava o resultado no fim,
então parar no limite perderia tudo o que já rodou; e ele quase não chama LLM (usa as especificações
gravadas). `scripts/propose_crash_lines.py` já parava no erro.

## Item 24: skill `llm-esbmc-pipeline`

A skill ainda descrevia os modos da V1 (esbmc-only, llm-only, ensemble), que não existem mais. Foi
reescrita para a CLI atual: modos `hybrid`, `benchmark` e `scan`, `--v2-stage`, fluxo do motor verify,
self-healing, nível 2, tabela das opções, saídas, códigos de saída (inclusive o 3 do item 23), custo
(item 25b), vereditos de `verify/outcome.py`, mapa dos arquivos e dataset. Cada opção citada foi
conferida contra `build_parser()` de `src/main.py` (só `--unwind` e `--multi-property` não estão lá,
porque são opções do ESBMC). Não há travessão no texto.

**Atenção:** a pasta `.claude/` está no `.gitignore`, então a skill não aparece no `git diff`. A versão
nova está em `.claude/skills/llm-esbmc-pipeline/skill.md` dentro do worktree e precisa ser copiada à
mão para `~/mestrado/llm_esbmc/.claude/skills/llm-esbmc-pipeline/skill.md`.

## Item 25a: `.gitattributes`

Arquivo novo na raiz: `* text=auto eol=lf`, tipos binários (pdf, png, jpg, zip, pptx etc.) e
`*.diff`, `*.patch` como `-text`. O `-text` dos patches é uma escolha minha: um patch precisa guardar os
bytes do arquivo a que se aplica, e `dataset/disciplina_pgene601/patches/cps_pyrtcm_34.diff` tem
finais de linha misturados. **Decisão da Fernanda:** confirmar se quer os patches fora da conversão.

**Medição** (sem renormalizar nada): `git ls-files --eol` mostra 179 arquivos com CRLF e 4 mistos no
índice. Comparando `git hash-object --stdin-paths` (que aplica o `.gitattributes`) com o blob do índice
(`git ls-files -s`), **182 arquivos mudariam** numa renormalização: 111 em `dataset/harness_bugs_reais`,
67 em `dataset/v1_sintetico`, 2 em `dataset/disciplina_pgene601`, 1 em `docs/experimentos` e o
`.gitignore`. Quase todos são do dataset; renormalizar muda os bytes (não as linhas) desses arquivos,
então qualquer hash de arquivo do dataset guardado em relatório antigo deixaria de bater. Por isso
isso fica para uma mudança separada, decidida por ela. (`git add --renormalize --dry-run .` lista todos
os 4257 arquivos e não serve para contar.)

## Item 25b: custo em US$ na telemetria

- Tabela única de preços por id de modelo em `src/research_pipeline/llm/pricing.py`, com os preços da
  API da Anthropic da skill `claude-api` (tabela de 06/10/2026): entrada, saída e leitura de cache por
  milhão de tokens; escrita de cache a 1,25x (5 min) ou 2x (1 h) da entrada. Sufixo de data no id
  (`-20251001`) é ignorado.
- Cada evento de `response_event` ganhou `cost_usd` e `billing`. Backend `anthropic`: preço da tabela.
  `claude_cli` e `codex`: `cost_usd` 0 e `billing: "assinatura"`. Modelo fora da tabela, chamada com
  erro ou outro provedor (openai, google, ollama): `cost_usd` `None` (não medido), nunca 0.
- `_summarize_v2_telemetry` soma `cost_usd` por etapa e conta `calls_without_cost`; a soma é `None`
  quando nenhuma chamada tinha preço. `scan_report.json` ganhou `cost_usd` da detecção e da
  especificação (só as chamadas desta sessão, como os tokens). O `llm_usage.jsonl` do agente por API
  também grava `cost_usd`.
- **Limites:** o Claude Haiku 5.5 usa o preço até 100 mil tokens de prompt; o `codex` conta como
  assinatura (ele roda pelo plano do ChatGPT), o que é uma leitura minha a conferir.

**Testes.** `tests/test_telemetry.py` (+8), `tests/test_main_v2.py` (+1), `tests/test_scan_pipeline.py`
(+1). Mutação: 7 de 7 mudanças (assinatura sem custo, modelo desconhecido, peso da escrita de cache,
sufixo de data, soma vazia, total por etapa, custo do scan) fazem teste falhar.

## Item 13: self-healing ligado por padrão

No código congelado (commit `7917192`) o padrão era `--heal none` (`src/main.py:248`). A cópia
principal do repositório tinha a mudança para `error+kb` ainda sem commit; repeti o mesmo texto aqui
para a junção não dar conflito. Agora:

- `src/main.py:248`: `default="error+kb"`. O mesmo parser serve ao `hybrid`/`benchmark`
  (`src/main.py:670`, `build_healer(args.heal, ...)`) e ao `scan` (`src/main.py:791`).
- Teste novo `test_self_healing_is_on_by_default` (hybrid e scan) em `tests/test_main_v2.py`.
- `scripts/v2_replay_specs.py:73` continua com `--heal none` de padrão: é o script que refaz rodadas
  antigas, e mudar o padrão dele mudaria o que essas reproduções medem. Deixei como está.

**Ponto para a Fernanda decidir:** o fingerprint do checkpoint do modo hybrid (`_v2_fingerprint`) não
inclui `--heal`. Uma rodada começada com o padrão antigo (`none`) e retomada com `--resume` depois
desta mudança mistura casos sem e com self-healing sem avisar. O scan não tem esse problema: o healer
entra no fingerprint dele e a retomada é recusada.

## Suíte e lint

- Suíte completa (`python -m pytest -q`, dividida em duas metades dos arquivos de teste para caber no
  teto de 10 min cada): **1447 passaram, 1 pulado, 0 falhas** (741 + 1 pulado em 6 min 32 s; 706 em
  3 min 09 s). A suíte inteira de uma vez passa de 10 min nesta máquina.
- `pylint` 4.1.3 (achado no cache do `uv`; não está no PATH nem no `.venv`), com `--disable=C,R`, nos
  arquivos mudados: nota 9,90. Os avisos que sobram já existiam (`broad-exception-caught` nos laços
  que de propósito pegam qualquer erro, `import-error` de `dotenv`/`pytest` porque esse pylint roda
  em outro ambiente, um `possibly-used-before-assignment` antigo em `agent_arm.py:475`). O único aviso
  novo (argumento sem uso num teste) foi corrigido. O `ruff` do `.venv` não acusa erro de pyflakes
  (F); o resto é estilo que já existia (ordem de imports, `noqa` sem uso).
