# Skill `/self-healing` interativa com o caderno de lições compartilhado com o lote

Data: 02/11/2026. Item "Skill `/self-healing` interativa com arquivo de lições compartilhado com o lote" da seção
Depois do `docs/projeto/PLANO_2026-10-19.md`, puxado antes da tag `v2-congelado-2026-11b` (decisão da Fernanda).

## Por quê

- O caderno de lições já existe: `src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md` (uma regra,
  aprovada em 27/10). Só o braço de agente o lê (`install_project_skills`).
- O self-healing do lote (`verify/healing.py`) não lê o caderno: o que se aprende num caso não chega aos outros.
- Não há como consertar um caso à mão vendo cada passo. A Fernanda quer aprender self-healing com casos reais do
  repositório (handoff do harness de agente) e decidiu que o caderno só recebe regra aprovada por ela.

## Objetivos

1. **Comando `/self-healing <caso>`** na extensão (`extension/commands/self-healing.md`): pega um caso que parou sem
   veredito do ESBMC (harness e original de uma rodada do braço de agente, ou um par original + harness à mão),
   roda o ESBMC, mostra o erro e consulta as regras (`regras-harness`, `reparos-aprendidos` e a documentação do
   ESBMC). Propõe **uma** reescrita por vez, explicando em português o que muda e por que o comportamento da
   função não muda. Depois confere a preservação do corpo e roda o ESBMC de novo, até o veredito ou 5 tentativas.
2. **Lição proposta, nunca gravada sozinha**: quando uma reescrita faz o ESBMC chegar a veredito, o comando monta
   a regra no formato do caderno e pergunta se pode gravar; só grava com "sim".
3. **Lote lê o caderno**: o prompt do `healing.py` recebe as regras aprovadas do caderno, e a versão (hash do
   arquivo) entra no resultado, como já acontece no braço de agente.

## Fora do escopo

- Gravar lição automaticamente, ou a partir do lote.
- Rodada nova para medir o efeito do caderno no lote: fica para a Fase 3 (gasta LLM).

## O que não pode acontecer

- Reescrita que muda o corpo da função alvo ou da função de fora que a chama: o comando confere com o mesmo
  `target_preserved` da validação e desfaz a tentativa quando der falso.
- Lição no caderno sem o "sim" dela, ou fora do formato (título, erro, o que fazer, caso de origem, data).

## Decisões de desenho

- Dois scripts pequenos que o comando chama, para a regra não depender do modelo lembrar:
  `scripts/check_preserved.py ORIGINAL HARNESS FUNCAO [EXPRESSAO]` (imprime `preservado` ou `alterado`, código de
  saída 0 ou 1) e `scripts/add_repair.py --title --error --what --case` (confere o formato e acrescenta a regra
  com a data do dia antes da seção "Format of an approved repair").
- O lote recebe só as regras aprovadas (as seções `###` antes de "Format of an approved repair").
- Comando e mensagens em português, como o `/verificar-repo`.

## O que fica para quem implementa

- O texto exato do comando, seguindo o formato do `verificar-repo.md`.
- Onde as regras entram no prompt do `healing.py` (sugestão: depois do erro do ESBMC, antes da documentação).
- Testes: os dois scripts (preservado, alterado, formato inválido, inserção no lugar certo) e o prompt do lote com
  e sem regras.
