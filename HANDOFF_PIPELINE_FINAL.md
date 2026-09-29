# Handoff: fechar o pipeline V2 (LLM detecta, ESBMC confirma)

## Objetivo da usuária (não mudar)

```
código Python real -> LLM aponta onde está o bug -> LLM constrói o código para o ESBMC -> ESBMC confirma ou refuta
```

Terminar isso com um número final. Não acrescentar camadas novas ao pipeline.
Não usar Docker. Não commitar sem pedido explícito. Sem Co-Authored-By de IA.
Nunca usar travessão em texto para ela. Confirmar custo antes de qualquer
chamada paga de API.

## Estado atual (o que já existe e funciona)

- O pipeline V2 já roda de ponta a ponta:
  ```
  PYTHONPATH=src .venv/bin/python src/main.py --mode hybrid --v2-stage end-to-end \
    --input dataset/v2_real_world/detection \
    --ground-truth dataset/v2_real_world/ground_truths.json \
    --model <modelo> --synth-backend openai --synth-model <modelo> \
    --output-dir artifacts/v2/<nome>
  ```
- Rodada de referência: `artifacts/v2/e2e-2026-09-27-gpt-4o-mini-single/v2_report.json`.
  Funil: 102 bugs; 34 detectados na categoria certa (118 falsos, precisão 0,22);
  29 foram à síntese; 21 harness compatíveis; 2 confirmados no código real.
  Perdas por etapa: síntese 24, grounding 6, abstração 1, verificação 1.
  109 de 135 hipóteses caíram no harness escalar (não testa o código real).
- Rodada `two_stage` (`artifacts/v2/e2e-2026-09-28-gpt-4o-mini-two-stage`) foi
  interrompida e nunca terminou; retomar com a mesma configuração + `--resume`.

## Causas medidas (com evidência)

1. Recortes do dataset sem dependências: em 68 de 90 casos elegíveis a função
   alvo usa nome que o próprio arquivo `detection/` não define (imports e
   helpers cortados). A auditoria anterior continua válida: ela verificou
   proveniência e os harnesses manuais de `bugs/`, não isso.
   Correção pronta: `scripts/fetch_v2_full_sources.py` baixa o arquivo
   original no buggy_commit, aceita só se a função for AST-idêntica
   (docstrings ignoradas) e grava `dataset/v2_real_world/detection_full/` +
   `manifest_full.json` (89 de 116 batem). Com isso, casos autocontidos
   passam de 22 para 66 de 90. Helpers de OUTROS arquivos do projeto
   (ex.: `thefuck.utils.replace_argument`) continuam ausentes.
2. 46% das funções são métodos de classe; `esbmc --function` não constrói o
   objeto (`method_entry`).
3. gpt-4o-mini é fraco para gerar código estruturado: 0 de 27 reescritas
   aceitas pelo ESBMC na rodada com stubs. Em setembro, na síntese escalar,
   gpt-4o acertou 3/3 onde o mini acertou 2/3.
4. Detecção confunde categorias (invalid_precondition vs none_misuse; quase
   nunca variable_misuse). Ver `docs/projeto/complemento_apresentacao_2026-09-23.md`, slides 9 a 12.

## Plano final (executar nesta ordem)

1. **Verificar no arquivo completo, detectar no recorte.** Adicionar a
   `run_pipeline_scan` (`src/research_pipeline/scan/pipeline.py`) o parâmetro
   `verification_sources: str | Path | None = None`. No loop, antes de
   `_run_one`: se `Path(verification_sources) / Path(candidate.file).name`
   existe, chamar `_run_one` com `dataclasses.replace(candidate, file=<esse caminho>)`
   e depois fazer `result.candidate = candidate` (a avaliação mapeia pelo
   arquivo detectado). Expor como `--verification-sources` em `src/main.py`
   (passar a `run_pipeline_scan` e gravar no `config`). Teste: um candidato
   cujo recorte não tem o helper e cujo arquivo completo tem; o resultado deve
   manter `candidate.file` original. Rodar a suíte:
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`.
2. **Escolher o modelo forte.** Listar modelos da chave (`GET https://api.openai.com/v1/models`)
   e estimar custo pelo consumo de tokens da rodada de referência
   (`artifacts/v2/e2e-2026-09-27-gpt-4o-mini-single/llm_telemetry.json`).
   Apresentar o custo à usuária e esperar o teto aprovado. Alternativa sem
   custo por token: `--backend claude_cli --synth-backend claude_cli`.
3. **Rodada final** com o modelo aprovado, `--verification-sources
   dataset/v2_real_world/detection_full`, mesma configuração da referência
   no resto. Guardar em `artifacts/v2/<nome>`.
4. **Comparar** com a referência: tabela do funil (detecção, compatíveis,
   confirmado no código real, confirmado só na abstração) antes e depois.
   Se sobrar orçamento, retomar a `two_stage` para comparar detecção.
5. **Escrever uma página para o orientador** (tom acadêmico, sem código nem
   caminho de arquivo): funil antes/depois e as causas medidas acima.

## O que NÃO fazer

- Não continuar refinando o estágio de reescrita com gpt-4o-mini (não converge).
- Não criar novos portões/camadas; o pipeline não precisa de peça nova.
- Não mexer em `dataset/v2_real_world/detection/`, `bugs/`, `manifest.json`
  nem `ground_truths.json`; os arquivos completos ficam em `detection_full/`.
- Não ler `bugs/` nem gabarito em nada que alimente prompt ou gerador.

## Trabalho experimental já feito (desligado por padrão, pode ignorar)

`--rewrite-mode validated` (reescrita da LLM com portão AST, replay local,
testemunha no original, stubs declarados, até 4 rodadas com feedback do
ESBMC) e `src/research_pipeline/scan/rewrite_eval.py` (avaliação retomável,
`--shard/--shards`, `--max-total-tokens`). Resultados parciais em
`outputs/rewrite_*` (ignorados pelo git): 0 aceitos com gpt-4o-mini.
Conhecimento do ESBMC-Python para prompts: `src/research_pipeline/prompts/esbmc_python_knowledge.txt`
(já anexado aos prompts de driver e reescrita).
Detalhes: `PLANO_IMPLEMENTACAO_GENERICO.md`, `DESENHO_HARNESS_GENERICO.md`.

## Pendente de commit (verificar com `git status`)

Tudo do estágio de reescrita após os 8 commits por task, o conhecimento do
ESBMC nos prompts, âncora por comando, stubs, replay local, sharding,
`scripts/fetch_v2_full_sources.py`, `detection_full/` e `manifest_full.json`.
Rodar a suíte antes de commitar; mensagens sem Co-Authored-By.
