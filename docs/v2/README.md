# V2: detectar bugs em código Python real e confirmá-los com o ESBMC

Guia de uso. O desenho do método (regras, tipos aceitos, vereditos, limitações e referências) está
em [`desenho_motor_verify.md`](desenho_motor_verify.md).

## Fluxo

1. **Detecção (LLM):** cada função do arquivo é analisada em uma chamada; a LLM devolve a
   expressão suspeita, uma explicação, a propriedade violada e se o bug é verificável
   formalmente (`verifiable`). Só os verificáveis seguem para o ESBMC; os outros contam na
   detecção. Não há categoria (prompt em `src/research_pipeline/prompts/system_prompt_v2.txt`).
2. **Aterramento (AST):** a expressão precisa existir na função; senão, `GROUNDING_FAILED`.
3. **Recorte:** a função e o que ela usa são copiados do arquivo completo sem alteração lógica.
   Bibliotecas que o ESBMC não modela viram stubs; métodos ganham um `__init__` que cria o estado
   do objeto.
4. **Especificação (LLM):** a LLM descreve os tipos das entradas em JSON. Não escreve código.
5. **Harness:** montado pelo pipeline a partir do JSON.
6. **ESBMC** (`--unwind 5 --multi-property`), com até 2 reparos em caso de erro de conversão.
7. **Reexecução no CPython** do mesmo programa; o caso só é `CONFIRMED` quando ESBMC e execução
   concordam na exceção e na linha da hipótese.

## Comandos

Ponta a ponta (RQ1 e RQ3):

```bash
PYTHONPATH=src .venv/bin/python src/main.py \
    --mode hybrid --v2-stage end-to-end \
    --input dataset/bugs_reais/funcao_com_bug \
    --ground-truth dataset/bugs_reais/ground_truths.json \
    --verification-sources dataset/bugs_reais/arquivo_com_bug \
    --model gpt-4o-mini --synth-backend openai --synth-model gpt-4o-mini \
    --bound 5 --timeout 180 --output-dir artifacts/v2/e2e
```

Hipóteses do gabarito, só verificação (RQ2): troque `--v2-stage end-to-end` por
`--v2-stage synthesis`.

Linha de base do reparo: acrescente `--spec-strategy resample`.

Confirmação falsa: `--verification-sources dataset/bugs_reais/arquivo_corrigido
--verification-sources-strict` (verifica as versões corrigidas; todo `CONFIRMED` é falso).

Retomar uma rodada: repita o comando com `--resume`.

## Onde ler o resultado

`v2_verify_report.json`:

| Chave | Conteúdo |
|---|---|
| `verification.by_verdict` | contagem por veredito |
| `verification.success_at_k` | fração de hipóteses com veredito do ESBMC em até k chamadas da LLM |
| `evaluation.detection_by_location` | detecção por arquivo, função e expressão (RQ1) |
| `evaluation.triage` | acerto da triagem: dos bugs achados, quantos o ESBMC pode confirmar e foram enviados (`sent_when_should`) e quantos não pode e foram segurados (`held_when_should`); o gabarito é `failure_kind` |
| `evaluation.confirmed_by_location` | confirmações na função certa (RQ3) |
| `results[]` | uma entrada por hipótese: veredito, motivo, tentativas, transformações, reexecução |

Para recalcular vereditos depois de mudar a regra de confirmação, sem LLM nem ESBMC:
`python scripts/v2_reverdict.py <v2_verify_report.json>`.

## Braço experimental com agente

`scripts/v2_agent_arm.py` roda o Claude Code com o plugin ESBMC nos casos em que o motor parou.
O pipeline não confia no agente: roda o ESBMC e a reexecução por conta própria, e um harness que
altera o corpo da função é contado à parte (`AGENT_REWRITE_CONFIRMED`).

## Limites conhecidos do ESBMC-Python 8.5

Reprodutores mínimos em [`../projeto/repro_esbmc_none/`](../projeto/repro_esbmc_none/).
