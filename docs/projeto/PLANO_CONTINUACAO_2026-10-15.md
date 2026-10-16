# Plano de continuação (15/10/2026) para o Codex

Repositório: `/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc`, branch `master` (trabalhar direto em
master, sem branch nova). Regras da Fernanda: não usar travessão, não commitar sem ela pedir, nunca pôr
IA como coautor, registrar toda rodada em `docs/experimentos/README.md` (data, pasta, commit, comando,
resultado), reportar primeiro o delta da métrica final. Avisar o custo antes de rodar algo que gaste API
paga. A OpenAI API está **sem crédito**; LLM só via Claude Code CLI (`claude_cli`, assinatura) ou Codex
CLI (`codex`, plano).

## Métrica e estado

- Métrica: bugs do gabarito confirmados **na linha do gabarito** (ESBMC acha a violação e o replay no
  CPython do código ORIGINAL levanta a mesma exceção nessa linha). **Hoje: 12** (av_real_01,
  oob_real_01, oob_real_02, bip_luigi_21, bip_pandas_33, ip_real_14, nm_real_14, dz_real_03,
  oob_real_03, oob_real_05, tm_real_10, oob_real_10).
- Código congelado na tag `harness-freeze-2026-10-15` (commit 88ad57a). Tudo até ali está commitado.
- ESBMC: master 333d07cc8a em `~/esbmc-master/build/src/esbmc/esbmc`, sempre com
  `--no-pointer-check --no-align-check` (wrapper: `artifacts/v2/final-2026-10-15/esbmc.sh`).
- Rodar coisa pesada em paralelo causa ESBMC_TIMEOUT falso; casos perto de 180 s oscilam.
- Não usar `pkill -f` com padrão que case com a própria linha de comando; matar por PID.

## Tarefa 1: terminar a rodada final (passo 4)

A rodada `artifacts/v2/final-2026-10-15` parou na detecção (arquivo 183/277) quando a sessão caiu.
Tem checkpoint. Retomar (assinatura do Claude, sem custo de API):

```
setsid nohup artifacts/v2/final-2026-10-15/run.sh --resume > artifacts/v2/final-2026-10-15/run_resume.log 2>&1 < /dev/null &
```

`run.sh` = comando base com prompt A5 (`--v2-variants A1,A2`), `claude_cli` Sonnet 5.5 para detecção e
spec, ESBMC master pelo wrapper, `--bound 5 --timeout 180`, `ulimit -v 8000000`. Se o `--resume`
reclamar de fingerprint, conferir que nada em `src/` mudou desde a tag (a Tarefa 2 não pode ser aplicada
antes de a rodada terminar).

Depois, o orquestrador nas hipóteses sem veredito formal (LLM via Codex CLI, sem custo de API):

```
.venv/bin/python -W ignore scripts/v2_orchestrate.py artifacts/v2/final-2026-10-15/v2_verify_report.json \
  --arms dynamic,llm_input,pinned,api_agent --api-backend codex --api-agent-everywhere \
  --esbmc artifacts/v2/final-2026-10-15/esbmc.sh --timeout 180 \
  --fixed-sources dataset/bugs_reais/arquivo_corrigido --out artifacts/v2/final-2026-10-15/orq
```

Conferir o nome exato do relatório que o `main.py` grava na pasta. Contar a métrica pelo
`summary.confirmed_at_bug` do `orchestrated.json` mais os CONFIRMED do nível 1 que estão na linha
(`research_pipeline.v2_evaluator.at_bug_line`). Vereditos do agente que **não contam**: `STUB_INDUCED`
(exceção vem de stub inventado), `FIXED_ALSO_FAILS` (versão corrigida também quebra),
`CONFIRMED_SIMPLIFIED`/`TARGET_ALTERED` (corpo do alvo alterado). Registrar como "Fase 14" no README de
experimentos (a seção já existe, completar).

## Tarefa 2: regras novas do harness (feitas depois do congelamento, NÃO aplicadas em master)

Estão no patch `docs/projeto/regras_pos_congelamento_2026-10-15.patch` (também no worktree
`../llm_esbmc-rules`, HEAD destacado em 88ad57a; pode remover com `git worktree remove ../llm_esbmc-rules`
depois de aplicar). Conteúdo:

1. `compat.drop_project_decorators`: tira decoradores definidos no próprio programa só na cópia do ESBMC
   (o ESBMC recusa o `wrapper(*args, **kwargs)`; o replay mantém o decorador).
2. `compat.split_conditional_assignments`: `g = a if c else (lambda ...)` vira `if c: g = a` /
   `else: g = ...` (provado: ESBMC recusa IfExp com ramos função/lambda, aceita if/else). Acrescenta
   uma linha; por isso `render_program` recalcula `driver_start` e a faixa do alvo na cópia do ESBMC, e
   `pytest_gen._source_without_driver` agora acha a linha do driver sozinho.
3. `compat._unused_definitions`: uma definição citada só por ela mesma (recursão,
   `partial(deprecated, ...)`) deixa de contar como usada.

Suíte rápida passou com o patch (794). **Falta:** testes unitários das 3 regras (um por regra, que falhe
sem a regra) e a análise da medição abaixo.

Medição já rodada (specs gravados, sem LLM), em `artifacts/v2/rules-after-freeze-2026-10-15/full`
(`report_0of2.json`, `report_1of2.json`). Comparar com `artifacts/v2/esbmc-master-lote5full-2026-10-14/
merged_report.json` (referência; NÃO com a rodada de 05/10): quantos chegam ao ESBMC, UNSUPPORTED, e
principalmente CONFIRMED na linha. Parcial visto: bip_youtube_dl_3 virou CONFIRMED (checar se é na linha
do gabarito; só conta se for). ip_real_19 e oob_real_11 passam do erro antigo e param no próximo
(ip_real_19: erro interno do ESBMC `json type_error.302` em `tuple(filter(None, x[slice]))`, candidato a
issue para o Lucas; oob_real_11: tabela importada de outro módulo vira classe vazia e é indexada com str).

**Resultado da medição (analisado em 15/10):** CONFIRMED 13 → 20 e ESBMC_TIMEOUT 11 → 4, mas as 7
viradas para CONFIRMED são timeouts do lote 5 (máquina carregada) ou o av_real_01 que oscila; nenhuma vem
das regras novas. Na linha do gabarito: av_real_01, dz_real_03, ip_real_22, oob_real_01/02/03/05,
tm_real_10, todos já contados ou já vistos no lote 5 (ip_real_22 não conta: o gabarito é resultado errado,
`failure_kind: resultado_errado`; a confirmação é um AttributeError com `command.stderr` None na mesma
linha, outro defeito). Nenhuma perda. **Métrica segue 12; regras neutras.** UNSUPPORTED 105 → 109 e
MISSING_DEPENDENCY 44 → 40: casos que passaram do erro antigo e pararam no seguinte.

Como as regras não reduzem a métrica, aplicar o patch em master **depois** que a rodada final terminar
(`git apply docs/projeto/regras_pos_congelamento_2026-10-15.patch`), escrever os testes, rodar a suíte
(`timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`) e
reaplicar sobre os specs da rodada final sem LLM:

```
scripts/v2_replay_specs.py artifacts/v2/final-2026-10-15/<relatorio>.json \
  --esbmc "$HOME/esbmc-master/build/src/esbmc/esbmc --no-pointer-check --no-align-check" \
  --timeout 180 --shard i/2 --out artifacts/v2/final-2026-10-15-regras
```

(2 shards em paralelo no máximo, `ulimit -v 4500000`, `-W ignore::SyntaxWarning`).

## Tarefa 3: bloqueios que sobram (só se render)

Analisado em bugs na linha do gabarito; cada regra tende a destravar só o passo seguinte:
- "Could not resolve type of receiver" (bip_pandas_133 `cls._AXIS_ALIASES.get`, bip_thefuck_4
  `proc.stdout.read()` em `_Opaque`, oob_real_14 `os.environ.get` em nível de módulo: tentar remover
  atribuições de módulo não lidas pelo alvo).
- Parâmetro tipado `int` no spec mas usado com `.groups()`/subscrito (ip_real_32, oob_real_13): checagem
  de consistência do spec que rejeita e devolve ao LLM.
- `*args/**kw` em funções do projeto: ESBMC aceita `args: list[T], kw: dict[str, T]` explícitos
  (provado), mas vm_real_02 usa `Or(*s, ...)` e `type(s)(...)`, dinâmico demais.
- SPEC_FAILED "stub sem tipo de retorno" cita membros de fora do arquivo; deixar para o reparo do LLM.

## Tarefa 4: depois da métrica final

- 47 bugs da disciplina (`dataset/disciplina_pgene601`) e modo scan num repo real
  (`src/main.py --mode scan`, doc `docs/projeto/modo_scan_2026-10-14.md`): avisar custo antes.
- Rascunhos de issue para os reprodutores 19 a 44 (`docs/projeto/possiveis_problemas/`) para o Lucas:
  não postar sem confirmação.
