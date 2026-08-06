# Artefatos de Reprodutibilidade — ISE 2026

Este diretório reúne os artefatos citados no artigo "Um pipeline híbrido para
detecção inteligente e confiável de bugs e code smells em Python", submetido
ao 5th Brazilian Workshop on Intelligent Software Engineering (ISE 2026).

Conteúdo:

- `prompt/system_prompt.txt` — template completo do prompt enviado ao modelo
  de linguagem na etapa *Analyzer*, com *persona prompting* e *Chain-of-Thought*.
- `pipeline/research_pipeline/` — código-fonte do pipeline híbrido:
  - `preprocess.py` — conversão de funções Python em AST/`CodeUnit`.
  - `llm/` — chamada ao modelo, normalização de achados e validação
    estrutural por AST (`findings.py`, `categories.py`, `schema.py`).
  - `ast_utils.py` — comparação estrutural de expressões contra a AST
    (filtro de alucinação para bugs verificáveis).
  - `pipeline.py` — orquestração dos Flows A, B e C, incluindo a chamada ao
    ESBMC-Python (`--function`, `--incremental-bmc`, `--assign-param-nondet`).
  - `report.py` / `full_report.py` — consolidação do relatório final.
  - `evaluator.py` — cálculo de P, R, F1, Acc, MCC, FCR e NRR.
- `dataset/labeled/` — dataset rotulado utilizado na avaliação (70 funções
  Python): `ok/` contém o código-fonte das funções (`bugs/`, `smells/`,
  `clean/`), `ground_truths/` contém as anotações manuais correspondentes.
- `results/v1_benchmark/` — logs e relatórios brutos do experimento (v1)
  reportado no artigo: um `benchmark_<modelo>.json` por modelo, agregando
  as métricas, e `per_file/<modelo>/` com a avaliação e os logs de execução
  do ESBMC-Python por função individual.

## Como reproduzir

1. O código completo do pipeline (incluindo dependências e scripts de
   execução) está no repositório principal, em `research_pipeline/`.
2. O dataset completo está em `dataset/labeled/` no repositório principal;
   a cópia aqui é somente para referência e empacotamento do artefato.
3. Os relatórios e logs brutos da avaliação preliminar (Flow A/B/C, por
   modelo e por arquivo) estão em `results/v1_benchmark/` nesta pasta, e
   também em `reports/json/v1_benchmark/` no repositório principal.
4. Para reexecutar a triagem por LLM, a validação estrutural por AST e a
   confirmação formal via ESBMC-Python, utilize `pipeline.py` apontando para
   os arquivos de `dataset/labeled/ok/`, comparando a saída contra
   `dataset/labeled/ground_truths/` por meio de `evaluator.py`.

## Ambiente de execução

Os experimentos foram executados com o ESBMC-Python versão 8.3.0. Os
modelos locais (deepseek-r1:7b e qwen2.5-coder:7b) foram executados via
Ollama versão 0.30.5, sob WSL2, em uma máquina com GPU NVIDIA RTX 3060
Laptop (6GB VRAM) e até 15GB de RAM disponíveis para o processo dentro do
WSL2.

## Escopo

Esta cópia é estática, referente à submissão ao ISE 2026. Alterações
posteriores ao pipeline ou ao dataset devem ser consultadas diretamente no
repositório principal.
