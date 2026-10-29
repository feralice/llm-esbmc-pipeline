---
name: verificar-repo
description: Varre um repositório Python, confirma bugs com o ESBMC e mostra o relatório (confirmados com teste, suspeitas à parte)
arguments:
  - name: pasta
    description: A pasta do repositório a varrer
    required: true
  - name: foco
    description: O que priorizar, em texto livre (opcional)
    required: false
---

# Verificar um repositório

Argumentos: $ARGUMENTS (o primeiro é a pasta; o resto, se houver, é o foco).

1. **Achar o pipeline.** Use a variável de ambiente `LLM_ESBMC_HOME` (a pasta do repositório llm_esbmc). Se
   ela não existir, pergunte a quem usa onde o pipeline está e pare até ter a resposta. Daqui em diante, `$HOME_P`
   é essa pasta e a saída vai para `$HOME_P/artifacts/extensao/<nome da pasta varrida>`.

2. **Simular, sem gastar.** Antes de qualquer `cd`, guarde a pasta como caminho absoluto e o foco numa variável
   entre aspas simples (troque cada `'` do foco por `'\''`), para que nenhum caractere do foco vire comando:

   ```bash
   PASTA=$(realpath "<pasta>")
   FOCO='<foco, ou vazio>'
   cd "$HOME_P" && .venv/bin/python src/main.py --mode scan --input "$PASTA" --output-dir "<saida>" \
     --backend claude_cli --scan-rank pagerank --scan-focus "$FOCO"
   ```

   Leia `<saida>/scan_selection.json` e diga, em poucas linhas: quantas funções o grafo escolheu, as cinco
   primeiras e a estimativa de tokens da detecção. Lembre que a confirmação chama o agente uma vez por hipótese.

3. **Pedir confirmação.** Pergunte se pode gastar a assinatura nessa varredura, sugerindo `--scan-limit 5` num
   repositório grande. Sem um sim explícito, pare aqui: a simulação já ficou salva.

4. **Rodar.** Com o sim, repita o comando do passo 2 acrescentando `--yes --scan-verify agent` (e o
   `--scan-limit` combinado). Pode demorar: rode em segundo plano e avise quando terminar. Confira o código de
   saída: diferente de 0 quer dizer que parte da detecção falhou, e o relatório começa listando essas falhas.

5. **Mostrar o resultado.** Leia `<saida>/relatorio.md` e apresente, com o que o relatório traz, nesta ordem:
   - as falhas da detecção, se houver (funções que não foram analisadas);
   - os bugs **confirmados pelo ESBMC**, cada um com a expressão, a entrada que quebra e o teste, quando houver;
   - os confirmados só em código simplificado e os barrados pelos controles, como pistas, não como bugs;
   - as **suspeitas do LLM**, sempre rotuladas como suspeitas, com o motivo de não terem sido confirmadas.

   Nunca apresente uma suspeita como bug confirmado, e não acrescente detalhe que o relatório não tem.
