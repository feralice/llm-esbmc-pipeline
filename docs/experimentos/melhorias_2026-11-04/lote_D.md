# Lote D: motor verify, braço de agente e orquestrador (04 e 05/11/2026)

Feito por IA (Claude Code), numa cópia isolada do repositório, sem commit. Nenhuma chamada a LLM pago nem
ao `claude -p`: todos os testes usam agentes e ESBMC falsos. Nada foi medido com o ESBMC neste lote; a única
medição é a contagem do item 9, que não roda o ESBMC.

Suíte inteira: `timeout 600 .venv/bin/python -m pytest -q -p no:cacheprovider` deu 1423 passados e 1
pulado (7 min 40 s). Cada teste novo foi conferido por mutação: estragar a regra no código faz o teste falhar
(10 de 10 mutações derrubadas).

## Item 7: hipótese de resultado errado no braço de agente e no orquestrador

**O que era:** a hipótese de valor (`VALUE_ORACLE`: nada levanta exceção, o LLM escreve `returns` e uma
pós-condição) só rodava no motor de regras. O roteamento devolvia lista vazia e o agente era pulado.

**O que mudou:**

- O agente recebe a pós-condição que o motor já aceitou (a última especificação sem problemas, lida de
  `attempts` por `value_oracle.engine_property`). O prompt pede que o driver guarde o retorno em
  `_esbmc_result` e termine com exatamente o `assert` que o motor escreveria (mesma função
  `render.property_assert`, usada agora pelos dois).
- O pipeline não confia no agente: confere que o harness tem esse `assert` uma vez só, nenhum outro `assert`
  novo, e que `_esbmc_result` recebe o valor direto de uma chamada da função alvo, antes do `assert`. Sem isso,
  `AGENT_FAILED`. Sem pós-condição do motor, `AGENT_FAILED` antes de chamar o agente (não gasta sessão).
- O veredito usa a mesma regra do motor: `value_verdict`, controle com a versão corrigida (`check_fixed`) e
  `apply_control`. A regra virou uma função só, `value_oracle.value_outcome`, chamada pelo motor e pelo agente.
- Corpo da função alterado pelo agente não confirma resultado errado (a reexecução fica indisponível e o
  veredito vira `UNVALIDATED`).
- Roteamento: hipótese de valor vai só para os braços de agente (`api_agent`, `claude_agent`); busca dinâmica,
  entradas do LLM e ESBMC fixado procuram exceção e continuam de fora. `VALUE_CONFIRMED`, `VALUE_VIOLATION` e
  `PROPERTY_REJECTED` contam como veredito formal e encerram a sequência. `--api-agent-everywhere` e o
  `--agent-fallback` agora incluem hipóteses de valor.
- A reexecução reconhecia a violação só num driver chamado `_esbmc_main`; agora reconhece pela linha do
  `assert`, para aceitar o driver do agente com outro nome.

**Arquivos:** `src/research_pipeline/verify/agent_arm.py`, `value_oracle.py`, `render.py`, `routing.py`,
`orchestrator.py`, `loop.py`, `replay_worker.py`; `scripts/v2_orchestrate.py`, `scripts/v2_agent_arm.py`,
`scripts/v2_agent_reverify.py`.

**Testes:** `tests/test_verify_agent_value.py` (novo: confirmação, propriedade rejeitada, sem versão
corrigida, cinco harnesses que fogem da propriedade, sem pós-condição, corpo alterado);
`tests/test_verify_value_metric.py` (atualizado: antes exigia que valor não tivesse braço, decisão 11 do
desenho do oráculo, que este item muda); `tests/test_v2_agent_arm_script.py`.

**Limite:** casos em que o motor nunca aceitou uma especificação (por exemplo `SPEC_FAILED` sem nenhuma
tentativa válida) não têm pós-condição e o agente não roda. Decidir se o próprio agente pode escrever a
pós-condição fica com a Fernanda.

## Item 8: controle com a versão corrigida mais fiel

**O que mudou:**

- Além da função alvo, o controle troca as outras funções do mesmo arquivo que a correção mudou
  (`value_oracle.changed_helpers`). Só troca uma função que o programa copiou igual ao original com bug: o que
  o harness gerou (um `__init__` de receptor, um stub) fica como está. Antes, se a correção estava só num
  helper, o controle dizia "a versão corrigida não muda a função" e não rodava.
- A reexecução agora anota quem pediu cada valor nondet (`função:intrínseca`, campo `draws`). Se a versão
  corrigida pede os mesmos valores em outra ordem, cada valor iria para outra entrada: o controle vira
  indisponível ("draws the nondet values in another order"), e o veredito fica `VALUE_VIOLATION`, que não conta.

**Arquivos:** `value_oracle.py`, `replay.py`, `replay_worker.py`, `loop.py`.

**Testes:** `tests/test_verify_value_oracle.py` (helper trocado e linha da propriedade movida; definição
gerada nunca trocada; ordem diferente vira inconclusivo, mesma ordem roda).

## Item 9: guarda do chamador no harness

**O que mudou:** com `spec_context="callers"` (o mesmo contexto que já ia para o prompt), o motor lê as
guardas que todo ponto de chamada tem sobre o argumento e as põe no harness como `__ESBMC_assume`.

- Formas lidas: `x is not None`, `x is None`, `if x:`, `len(x) <op> número`, `x <op> número`,
  `isinstance(x, T)`; dentro de `if`, `else`, expressão condicional, `and`/`or`, e um `if ...: return`
  (ou `raise`, `continue`, `break`) antes da chamada no mesmo bloco.
- Só vale guarda sobre um nome simples, que não é reatribuído depois do teste. Só ficam as guardas presentes
  em todos os pontos de chamada; um ponto sem a guarda, um ponto que não se consegue ler ou a função usada
  como valor (`map(f, ...)`, `partial`) deixam o caso sem nenhuma.
- A tradução depende do tipo que a especificação deu: `len(s) > 0` para texto e listas, `x != 0` para
  números, `x is not None` só para tipo opcional. `isinstance` não vira assume (num harness tipado ele é sempre
  verdadeiro ou sempre falso); se a especificação dá um tipo que nenhuma chamada real passaria, ela é recusada
  com o motivo, como já acontecia com os fatos de uso.

**Arquivos:** `src/research_pipeline/verify/caller_facts.py`, `loop.py`; `scripts/v2_caller_guards.py` (novo,
só a contagem).

**Testes:** `tests/test_verify_caller_facts.py` (só guardas comuns; chamador sem guarda, reatribuição e uso
como valor; saída antecipada; tradução por tipo) e `tests/test_verify_value_loop.py` (o assume chega ao
programa só com o contexto de chamadores).

**Contagem (offline, sem ESBMC nem LLM):**

    .venv/bin/python -W ignore scripts/v2_caller_guards.py

Dos 289 casos de `ground_truths.json`: 275 ancoram (5 não ancoram, 9 sem arquivo); 119 têm algum chamador no
próprio arquivo; **2 ganham um assume**: `nm_real_24` (`len(sources) != 1`, do `else` de
`if len(sources) == 1`) e `bip_black_8` (`opening_bracket` verdadeiro). O número é baixo porque o conjunto
tem o arquivo com bug isolado (156 casos sem chamador) e a regra é conservadora.

**Limite:** sem o grafo do repositório (modo verify), só se veem os chamadores do mesmo arquivo; uma função
pública pode ter chamadores em outros módulos sem a guarda. No modo scan o grafo cobre o repositório.

## Item 14: sobras da revisão do harness de agente

- `scripts/v2_repair_candidates.py`: caso `STUB_INDUCED` (no veredito final ou na primeira tentativa) não
  gera candidato ao caderno de reparos. Teste em `tests/test_v2_repair_candidates.py`.
- `scripts/v2_agent_arm.py`: sem `esbmc_commit` no binário a rodada para com erro (código 2) antes de chamar o
  agente, em vez de só avisar. O único lugar que grava esse campo é `esbmc_identity` do próprio script; o
  binário de medição (`~/esbmc-master/esbmc.sh` aponta para `build-bw`) tem a marca `ESBMC built from
  d520a903ae...`, então as rodadas normais não param. Teste em `tests/test_v2_agent_arm_script.py`.

## Item 15: consultor com `attempts` vazio

O `consult.py` era um rascunho dentro de `artifacts/` (fora do git). Virou `scripts/v2_consult.py`: um caso
recusado antes do harness (nenhuma tentativa guardou programa, como `bip_pandas_7`) recebe só o original e
`recusa.txt` com o motivo, e a primeira pergunta do prompt muda para "por que o pipeline recusou antes do
harness". Casos com `opiniao.md` continuam pulados. Teste em `tests/test_v2_consult.py`. Conferido sem chamar o
agente no `mini_report.json` de 22/10: o `bip_pandas_7` monta a pasta e o prompt. O `nm_real_08` tem três
tentativas com programa e já rodava; no rascunho ele só não chegou a rodar porque o laço quebrou antes, no
`bip_pandas_7`. Rodar o consultor de novo usa a assinatura do Claude Code e fica para a Fernanda decidir.

    .venv/bin/python scripts/v2_consult.py artifacts/v2/teste-ab-2026-10-22/mini_report.json \
        --out artifacts/v2/teste-ab-2026-10-22/C

## Não feito

- `pylint` não está instalado nesta máquina (nem no `.venv`); usei `ruff check --select E,F,W,B` nos arquivos
  mudados. O que sobra é anterior a este lote (linhas longas antigas, `zip` sem `strict`).
- Nenhuma medição com o ESBMC: os itens 7 e 8 mudam vereditos só quando há hipótese de valor com versão
  corrigida, e a decisão de rodar fica com a Fernanda.
