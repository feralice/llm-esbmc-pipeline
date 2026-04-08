# Fluxo Completo do Protótipo LLM + ESBMC

Este documento explica o fluxo completo que construímos no protótipo de pesquisa para análise de código Python com apoio de LLM e validação formal com ESBMC.

O objetivo do pipeline é separar claramente:

- achados heurísticos, como `code smells`;
- suspeitas de bugs e vulnerabilidades;
- propriedades formais derivadas dessas suspeitas;
- validação formal feita pelo ESBMC;
- classificação final dos resultados.

## Visão Geral

O fluxo completo é:

1. o pipeline recebe um arquivo Python;
2. faz um pré-processamento estrutural;
3. envia a unidade de código para um analisador heurístico;
4. esse analisador pode ser:
   - um backend `mock`, puramente determinístico;
   - ou um backend real com a OpenAI Responses API;
5. os achados verificáveis são convertidos em propriedades formais;
6. o código é instrumentado com `assert`;
7. o ESBMC é executado sobre o arquivo instrumentado;
8. o sistema consolida os resultados em um relatório final.

## Mapa dos Arquivos no Fluxo

### Entrada

- `experiments/research_pipeline_prototype/examples/minimal_index_division.py`

Este é um exemplo de arquivo Python real usado como entrada do pipeline.

### Orquestração

- `experiments/research_pipeline_prototype/scripts/run_research_pipeline.py`
- `experiments/research_pipeline_prototype/research_pipeline/pipeline.py`

Esses arquivos controlam a execução do fluxo completo.

### Pré-processamento

- `experiments/research_pipeline_prototype/research_pipeline/preprocess.py`

Responsável por:

- ler o código Python;
- separar funções e métodos;
- identificar operações relevantes;
- construir a representação intermediária usada pelo analisador.

### Análise heurística

- `experiments/research_pipeline_prototype/research_pipeline/llm_analyzer.py`

Esse módulo implementa dois modos:

- `mock`: analisador heurístico determinístico;
- `openai`: integração real com a OpenAI Responses API.

Ele é responsável por:

- detectar smells heurísticos;
- detectar bugs e vulnerabilidades suspeitos;
- explicar tecnicamente o raciocínio;
- indicar quais achados parecem verificáveis formalmente.

### Formalização

- `experiments/research_pipeline_prototype/research_pipeline/formalizer.py`

Converte achados heurísticos verificáveis em propriedades formais locais.

Exemplos:

- `values[idx]` -> `0 <= idx < len(values)`
- `item // denom` -> `denom != 0`

### Instrumentação

- `experiments/research_pipeline_prototype/research_pipeline/instrumenter.py`

Gera um novo arquivo Python instrumentado, preservando o módulo original e inserindo os `asserts` na linha relevante.

Exemplos de arquivos gerados:

- `experiments/research_pipeline_prototype/artifacts/research-pipeline/instrumented/analyze_me_subscript_5_values_idx.py`
- `experiments/research_pipeline_prototype/artifacts/research-pipeline/instrumented/analyze_me_division_6_item_denom.py`

Quando o backend real está sendo usado, os nomes podem refletir o identificador gerado pela LLM.

### Verificação formal

- `experiments/research_pipeline_prototype/research_pipeline/esbmc_runner.py`

Esse módulo chama o ESBMC via terminal, usando `subprocess.run(...)`.

Ou seja, o pipeline executa internamente algo equivalente a:

```bash
esbmc arquivo_instrumentado.py
```

O runner coleta:

- `stdout`;
- `stderr`;
- `returncode`;
- status consolidado da verificação.

### Consolidação do resultado

- `experiments/research_pipeline_prototype/research_pipeline/report.py`

Esse módulo transforma os dados do LLM, da formalização e do ESBMC em uma classificação final.

### Saída final

- `experiments/research_pipeline_prototype/artifacts/research-pipeline/report.json`

Esse arquivo contém o resultado final do pipeline para cada achado.

## Etapa por Etapa

## 1. Entrada do código

O pipeline recebe um arquivo Python como entrada.

Exemplo:

```python
from typing import List

def analyze_me(values: List[int], idx: int, denom: int) -> int:
    item = values[idx]
    return item // denom
```

## 2. Pré-processamento estrutural

O pré-processamento não tenta provar bugs nem classificar resultados finais.

Ele apenas organiza o código em uma estrutura útil para o restante do pipeline.

Para cada função, ele extrai:

- nome;
- intervalo de linhas;
- parâmetros;
- type hints;
- operações críticas;
- loops;
- condicionais;
- asserts já existentes;
- métricas básicas.

No exemplo acima, ele detecta:

- `values[idx]` como acesso indexado;
- `item // denom` como divisão.

## 3. Análise heurística por LLM

Depois do pré-processamento, cada unidade analisável é enviada ao analisador.

No modo `mock`, isso é feito localmente por heurísticas.

No modo `openai`, o pipeline envia:

- o código da unidade;
- as operações detectadas;
- os metadados estruturais;
- instruções para retornar apenas JSON estruturado.

O resultado esperado inclui:

- `smell_heuristic`;
- `suspected_bug`;
- `category`;
- `explanation`;
- `evidence`;
- `metadata`.

## 4. Classificação inicial

Cada achado é classificado como:

- smell heurístico;
- bug suspeito;
- vulnerabilidade suspeita;
- verificável ou não verificável.

Essa etapa impede que um smell seja tratado como bug formal.

## 5. Formalização parcial

Se o achado for verificável, o pipeline gera uma propriedade formal correspondente.

Exemplo:

- suspeita: acesso fora dos limites
- propriedade: `0 <= idx < len(values)`

ou:

- suspeita: divisão por zero
- propriedade: `denom != 0`

## 6. Instrumentação

O sistema cria um novo arquivo instrumentado.

Esse arquivo:

- preserva o código original;
- insere um `assert` próximo da operação suspeita;
- é salvo na pasta `artifacts/.../instrumented/`.

Esses arquivos existem apenas para verificação formal; eles não substituem o código original.

## 7. Execução do ESBMC

O ESBMC é chamado via terminal sobre o arquivo instrumentado.

Exemplo:

```bash
esbmc experiments/research_pipeline_prototype/artifacts/research-pipeline/instrumented/analyze_me_division_6_item_denom.py
```

O ESBMC pode retornar:

- `VERIFICATION SUCCESSFUL`
- `VERIFICATION FAILED`
- erro de parsing/conversão
- timeout

## 8. Interpretação do resultado do ESBMC

É importante não confundir:

- erro operacional da ferramenta;
- falha de propriedade.

### Quando é erro operacional

Exemplos:

- `Cannot open file`
- `Parsing failed`
- `Converting failed`
- timeout

Nesses casos, a classificação tende a ser `inconclusive_case`.

### Quando é bug confirmado

Se o ESBMC mostrar:

- `[Counterexample]`
- `Violated property`
- `VERIFICATION FAILED`

isso significa que a propriedade foi realmente violada.

No contexto deste pipeline, isso é interpretado como:

- `formally_confirmed_bug`

Ou seja, `VERIFICATION FAILED` nao significa necessariamente erro da ferramenta; pode significar que o bug foi encontrado.

## 9. Consolidação final

O pipeline combina:

- achado da LLM;
- propriedade formal gerada;
- saída do ESBMC;
- interpretação final.

As classificações finais possíveis são:

- `smell_heuristic`
- `vulnerability_potential_with_partial_evidence`
- `unconfirmed_hypothesis`
- `formally_confirmed_bug`
- `inconclusive_case`

## Exemplo Real do Fluxo

No arquivo `minimal_index_division.py`, o pipeline detectou:

### Achado 1

- categoria: `out_of_bounds`
- expressão: `values[idx]`
- propriedade formal: `0 <= idx < len(values)`

Quando o ESBMC encontrou contraexemplo, o sistema classificou como:

- `formally_confirmed_bug`

### Achado 2

- categoria: `division_by_zero`
- expressão: `item // denom`
- propriedade formal: `denom != 0`

Quando o ESBMC encontrou `denom = 0` no contraexemplo, o sistema classificou como:

- `formally_confirmed_bug`

### Achado 3

- categoria: `missing_input_validation`
- tipo: `smell_heuristic`

Esse achado ficou apenas na trilha heurística.

## Como Executar

### Modo offline

```bash
python experiments/research_pipeline_prototype/scripts/run_research_pipeline.py experiments/research_pipeline_prototype/examples/minimal_index_division.py --esbmc-command esbmc
```

### Modo com OpenAI real

```bash
export OPENAI_API_KEY="SUA_CHAVE_AQUI"
python experiments/research_pipeline_prototype/scripts/run_research_pipeline.py experiments/research_pipeline_prototype/examples/minimal_index_division.py --llm-backend openai --llm-model gpt-5.4 --esbmc-command esbmc
```

## Leitura Conceitual Final

O papel de cada componente no fluxo é:

- `preprocess.py`: organiza o código;
- `llm_analyzer.py`: detecta, classifica e explica;
- `formalizer.py`: traduz suspeitas em propriedades;
- `instrumenter.py`: cria o arquivo verificável;
- `esbmc_runner.py`: chama o ESBMC;
- `report.py`: consolida a saída final.

Em termos de pesquisa, o fluxo implementa:

- detecção heurística com LLM;
- explicação em linguagem natural;
- formalização parcial de propriedades;
- validação formal com ESBMC;
- distinção entre smell, suspeita e bug confirmado.
