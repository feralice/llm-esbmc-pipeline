---
name: self-healing
description: Conserta, passo a passo e explicando cada reescrita, um harness que o ESBMC-Python recusou; propõe a lição para o caderno e só grava com a sua aprovação
arguments:
  - name: caso
    description: A pasta de uma rodada do braço de agente (lista os casos sem veredito) ou a pasta de um caso (cases/<id>)
    required: true
---

# Self-healing interativo

Argumentos: $ARGUMENTS.

Quem usa quer **aprender** self-healing: explique cada passo em português, com o erro real e o código real, sem
jargão desnecessário. Uma reescrita por vez; nunca várias de uma vez.

1. **Achar o pipeline.** Use a variável de ambiente `LLM_ESBMC_HOME` (a pasta do repositório llm_esbmc). Se ela
   não existir, pergunte onde o pipeline está e pare até ter a resposta. `$HOME_P` é essa pasta. O ESBMC é
   `~/esbmc-master/build-bw/src/esbmc/esbmc` quando existir; senão, `esbmc` do `PATH`.

2. **Escolher o caso.**
   - Se o argumento é a pasta de uma rodada (tem `agent_results.json`), liste os casos cujo `verdict` é
     `UNSUPPORTED`, `ESBMC_ERROR`, `ESBMC_TIMEOUT`, `BOUND_INCONCLUSIVE` ou `AGENT_FAILED`: id (os 12 primeiros
     caracteres de `harness_path` depois de `cases/`), função, veredito e o começo de `reason`. Pergunte qual e pare.
   - Se é a pasta de um caso (tem `original.py` e `harness.py`), pegue função e expressão suspeita na entrada de
     `agent_results.json` da rodada cujo `harness_path` aponta para essa pasta.

3. **Trabalhar numa cópia.** Copie `harness.py` para `<caso>/self-healing/harness.py` e trabalhe só nela; o
   harness da rodada é evidência e não muda.

4. **Ler as regras antes de mexer.** Leia `$HOME_P/src/research_pipeline/verify/skills/regras-harness/SKILL.md` e
   `$HOME_P/src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md` (o caderno de lições, o mesmo que o
   lote lê). Se o plugin do ESBMC estiver disponível, a skill dele também vale.

5. **Rodar o ESBMC e mostrar o erro.** Dentro de `<caso>/self-healing`:

   ```bash
   "$ESBMC" harness.py --unwind 5 --multi-property
   ```

   Mostre a primeira linha `ERROR:` (ou o motivo de não haver veredito) e explique em uma ou duas frases o que o
   ESBMC-Python não aceitou.

6. **Propor uma reescrita.** Mostre o trecho antes e depois, diga qual regra do caderno ou da skill ela segue (ou que
   é nova) e por que o comportamento da função alvo não muda. Pergunte se pode aplicar e pare até a resposta.

7. **Aplicar e conferir.**
   - Aplique a reescrita na cópia e rode:

     ```bash
     cd "$HOME_P" && .venv/bin/python scripts/check_preserved.py "<caso>/original.py" \
       "<caso>/self-healing/harness.py" "<função>" "<expressão suspeita>"
     ```

   - `alterado` (saída 1): o corpo da função alvo, ou da função de fora que a chama, mudou. Desfaça a reescrita,
     explique o que mudou e volte ao passo 6 com outra proposta.
   - Saída 2: não deu para conferir (arquivo faltando, harness que não é Python válido, função não encontrada).
     Mostre a mensagem e conserte isso primeiro; não conte como reescrita que mudou o corpo.
   - `preservado`: rode o ESBMC de novo (passo 5).

8. **Parar.** Pare quando o ESBMC chegar a `VERIFICATION FAILED` ou `VERIFICATION SUCCESSFUL`, ou depois de 5
   reescritas sem veredito. Em `VERIFICATION FAILED`, mostre a propriedade violada e diga que a confirmação de
   verdade passa pelo pipeline (reexecução no CPython e controles); nada aqui conta como bug confirmado.

9. **Propor a lição.** Se uma reescrita fez o ESBMC chegar a veredito, monte a regra no formato do caderno:
   título curto, a primeira linha `ERROR:` que ela resolveu, o que fazer, o caso de origem (id e bug) e a rodada.
   Mostre a regra e pergunte: "Posso gravar no caderno?". Só com um "sim" explícito rode:

   ```bash
   cd "$HOME_P" && .venv/bin/python scripts/add_repair.py --title "<título>" --error "<ERROR: ...>" \
     --what "<o que fazer>" --case "<id> (<bug>), reescrita <n>"
   ```

   Se o script recusar (formato ou título repetido), mostre o motivo e corrija com quem usa; a regra corrigida
   precisa de um novo "sim" antes de rodar o script de novo. Nunca edite o caderno à mão (Edit ou Write): só pelo
   script, e só com "sim".

10. **Resumo.** Diga o que foi tentado, o que funcionou, se a lição foi gravada e onde está a cópia do harness.
