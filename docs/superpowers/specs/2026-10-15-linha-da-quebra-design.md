# Linha da quebra no gabarito (subprojeto 1 de 4)

Data: 15/10/2026. Parte do plano de melhoria no dataset: (1) linha da quebra no gabarito, (2) sondas de
capacidade do ESBMC, (3) spec com contexto dos chamadores, (4) variantes de prompt.

## Objetivo

Um bug de exceção tem dois lugares: a linha que a correção muda (`expression`, a causa) e a linha onde a
versão com bug levanta a exceção (`crash_expressions`). Só 27 dos 111 bugs de exceção têm a segunda.
Nos outros, quando o LLM aponta a linha da quebra, a avaliação conta como erro. Na rodada final de
15/10, 44 bugs de exceção tiveram hipótese na função certa e expressão diferente do gabarito; parte
deles é esse problema de rótulo (ex.: bip_pandas_59, gabarito `window = self._get_window(other)`,
quebra na divisão logo abaixo).

**Sucesso:** todo bug de exceção sem `crash_expressions` recebe uma decisão revisada (linha da quebra
adicionada, ou "a quebra é a própria linha da causa"), com origem registrada, e a métrica é recalculada
nos relatórios existentes mostrando antes e depois separados.

**Fora do escopo:** bugs de resultado errado (178), mudar `expression`, mudar a regra de exceção
esperada da métrica, rodar o pipeline de novo.

## Fluxo

1. **Propor** (`scripts/propose_crash_lines.py`). Para cada bug com `failure_kind` diferente de
   `resultado_errado` e sem `crash_expressions`, o LLM (padrão `claude_cli` Sonnet, escolhível por
   `--backend/--model` como no resto do pipeline) recebe: a função com bug (`funcao_com_bug`), o patch
   (`patches/<id>.diff`), a `expression` do gabarito e a `failure_kind_note`. Devolve JSON
   `{"same_as_expression": bool, "crash_expressions": [str], "exception": str, "reason": str}`.
2. **Validar por código.** Cada item de `crash_expressions` precisa aparecer na função com bug
   (comparação por `expressions_equivalent`, a mesma da avaliação). Item que não aparece é descartado e
   anotado. Saída: `dataset/bugs_reais/crash_proposals.json` (uma entrada por bug, com a resposta
   bruta, o resultado da validação e o modelo). Retomável: bug já proposto não é refeito.
3. **Conferência do Claude Code.** Leio cada proposta contra o código e o patch e preencho
   `review: aceita | rejeitada | duvida` e `review_note` no mesmo arquivo.
4. **Revisão da Fernanda.** Tabela em `docs/projeto/revisao_linha_da_quebra_2026-10-15.md`: bug, causa,
   quebra proposta, exceção, parecer. Ela marca as que discorda.
5. **Aplicar.** As aceitas entram em `dataset/coleta_bugsinpy/labels.json` (campo `crash_expressions`) com
   `label_sources.crash_expressions = "llm_patch_revisado"`; o gabarito é regerado por
   `scripts/build_v2_bugsinpy.py`. Dos 84 bugs, 31 são da coleta BugsInPy; os 53 das coortes curadas
   (av/dz/ip/nm/oob/tm) não têm gerador e recebem o campo direto em `ground_truths.json`, `manifest.json`
   e `manifest_full.json`, como o commit 02d5785 fez com o ip_real_11. Um script aplica nos três
   arquivos de uma vez para não divergirem.
6. **Medir.** Recalcular localização da detecção e bugs confirmados na linha sobre
   `artifacts/v2/final-2026-10-15-codex` e os relatórios das rodadas anteriores, antes e depois. Registrar
   em `docs/experimentos/README.md`.

## Proteções da medida

- **Sem circularidade:** o LLM que rotula vê só código, patch e gabarito, nunca as hipóteses do pipeline.
  O mesmo modelo (Sonnet) faz detecção e rótulo; a dupla revisão (Claude Code e Fernanda) é o controle,
  e a dissertação reporta isso.
- **Exceção continua exigida:** para contar como confirmado, a exceção tem que ser a esperada
  (bip_scrapy_15 segue fora).
- **Antes e depois lado a lado:** a métrica antiga continua reportável.

## Erros

- Resposta que não é JSON: até 2 novas tentativas com a mensagem de erro; depois `failed`, sem bloquear
  os outros.
- Limite de uso do LLM: o script para, salva o que tem, e a próxima execução continua.
- Patch ausente: o bug é listado como `sem_patch` e vai direto para a revisão manual.

## Testes

`tests/test_propose_crash_lines.py`, LLM falso:
- expressão inexistente na função é descartada;
- `same_as_expression` não adiciona linha;
- retomada não chama o LLM para bug já proposto;
- aplicar grava `label_sources` e não toca bug rejeitado.

## Custo

84 chamadas ao `claude_cli` (assinatura, sem custo de API; consome limite de uso).
