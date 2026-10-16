# Resumo da noite 15 para 16/10/2026

Plano em vigor: `docs/projeto/PLANO_GERAL_2026-10-15.md`. Nada foi commitado, nenhum e2e ou experimento
rodou, o gabarito não foi aplicado. Suíte: **1058 testes passando** (era 808 no começo), duas rodadas seguidas.

## Esperando a Fernanda

1. **Revisar a tabela do gabarito:** `docs/projeto/revisao_linha_da_quebra_2026-10-15.md`. No topo está a
   lista do que olhar primeiro (8 quebras em dúvida, 5 rejeitadas, 14 corrigidas, 47 causas corrigidas).
   Depois da revisão: `PYTHONPATH=src .venv/bin/python scripts/propose_crash_lines.py apply`.
2. **Decidir o commit** de tudo (73 arquivos novos ou alterados).
3. **Aprovar ou ajustar as decisões** listadas na seção "Decisões tomadas sem a Fernanda" de cada spec
   em `docs/superpowers/specs/2026-10-16-*.md`.

## O que ficou pronto

| Item | Resultado | Onde |
|---|---|---|
| 1 Gabarito | causas tiradas do patch para os 289 bugs; quebras propostas pelo Claude para os 84 de exceção; 143 casos conferidos por revisores; avaliação aceita todas as linhas | `scripts/propose_crash_lines.py`, `dataset/bugs_reais/crash_proposals.json` |
| 2 Sondas | 57 sondas para 12 regras; a regra só desliga se o ESBMC instalado aceita a construção (com "gêmeo seguro" para não desligar por engano). No ESBMC master atual desligam 2 regras | `verify/capabilities.py`, `verify/probes/` |
| 3 Spec com contexto | o pedido de tipos ao LLM recebe chamadas da função no arquivo e fatos de uso; tipo contraditório pelo uso é rejeitado e volta ao LLM. `--spec-context none` é idêntico ao antigo | `verify/caller_facts.py` |
| 4 Prompts | A13 (exemplos parecidos, sem o próprio projeto) e A14 (citar a linha e a condição). Inspeção sem LLM: `scripts/print_detection_prompt.py` | `llm/example_pool.py` |
| 5 Oráculo de valor | A15: o LLM escreve a propriedade esperada, o harness faz `assert`, ESBMC busca violação, replay confirma no original e a versão corrigida não pode violar. Conferido no ESBMC real com programa mínimo | `verify/value_oracle.py` |

Uma revisão final do conjunto achou 2 problemas importantes no item 5 (decoradores no controle; função
igual vista como diferente) e alguns menores; todos corrigidos com teste antes.

## Avisos para o item 6

- O checkpoint pausado `artifacts/v2/final-2026-10-15-codex` não retoma mais (a configuração ganhou
  `spec_context`). A rodada final do item 6 começa do zero.
- Os comandos do item 6 estão no PLANO_GERAL (seção de cada item).
