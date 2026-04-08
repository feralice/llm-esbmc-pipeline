---
marp: true
theme: default
paginate: true
size: 16:9
title: Fluxo do Pipeline LLM + ESBMC para Python
description: Slides focados no fluxo do prototipo
---

# Fluxo do Pipeline LLM + ESBMC para Python

## Visao simples e detalhada do processo

**Ideia central**

- o codigo Python entra no pipeline
- a LLM analisa e gera achados
- o sistema separa o que e heuristico do que e verificavel
- o ESBMC valida formalmente o que for possivel

---

# Fluxo Geral

```mermaid
flowchart TD
    A[Codigo Python] --> B[Pre-processamento]
    B --> C[Analise heuristica por LLM]
    C --> D{Achado verificavel?}
    D -- Nao --> E[Smell heuristico]
    D -- Sim --> F[Formalizacao parcial]
    F --> G[Instrumentacao]
    G --> H[ESBMC]
    H --> I{Violacao encontrada?}
    I -- Sim --> J[Bug formalmente confirmado]
    I -- Nao --> K[Hipotese nao confirmada]
```

**Leitura do diagrama**

- o lado esquerdo representa a trilha heuristica
- o lado direito representa a trilha formal

---

# Etapa 1. Entrada

```mermaid
flowchart LR
    A[Arquivo Python] --> B[Funcao ou modulo analisado]
```

**O que entra**

- um arquivo Python real
- uma funcao
- um metodo
- ou um modulo completo

**Exemplo do prototipo**

- `minimal_index_division.py`

---

# Etapa 2. Pre-processamento

```mermaid
flowchart LR
    A[Codigo bruto] --> B[Segmentacao]
    B --> C[Extracao de tipos e parametros]
    C --> D[Deteccao de operacoes criticas]
    D --> E[Representacao intermediaria]
```

**O que essa etapa faz**

- separa funcoes e metodos
- extrai assinatura, parametros e tipos
- detecta operacoes relevantes
  - acesso indexado
  - divisao
  - loops
  - condicionais
  - asserts

**Importante**

Essa etapa nao diagnostica bug.  
Ela apenas organiza o codigo para a analise seguinte.

---

# Etapa 3. Analise Heuristica por LLM

```mermaid
flowchart LR
    A[Representacao intermediaria] --> B[LLM]
    B --> C[Smells]
    B --> D[Suspeitas de bug]
    B --> E[Suspeitas de vulnerabilidade]
    B --> F[Explicacao tecnica]
```

**O que a LLM faz**

- detecta smells
- detecta bugs suspeitos
- detecta vulnerabilidades suspeitas
- explica o raciocinio
- classifica inicialmente os achados

**O que a LLM nao faz**

- prova formal
- confirmacao matematica do defeito

---

# Etapa 4. Decisao: o achado e verificavel?

```mermaid
flowchart TD
    A[Achado da LLM] --> B{Pode virar propriedade formal?}
    B -- Nao --> C[Trilha heuristica]
    B -- Sim --> D[Trilha formal]
```

**Se nao for verificavel**

- permanece como smell ou risco heuristico
- segue apenas com explicacao textual

**Se for verificavel**

- segue para formalizacao
- depois instrumentacao
- depois ESBMC

---

# Trilha Heuristica

```mermaid
flowchart LR
    A[Achado nao verificavel] --> B[Explicacao textual]
    B --> C[Smell heuristico]
```

**Exemplos**

- `Long Method`
- `God Class`
- problemas arquiteturais
- riscos de manutencao

**Resultado final tipico**

- `smell_heuristic`

---

# Trilha Formal

```mermaid
flowchart LR
    A[Achado verificavel] --> B[Formalizacao parcial]
    B --> C[Instrumentacao]
    C --> D[ESBMC]
```

**Exemplos de achados verificaveis**

- acesso fora dos limites
- divisao por zero
- violacao simples de pre-condicao

---

# Etapa 5. Formalizacao Parcial

```mermaid
flowchart LR
    A[Suspeita] --> B[Propriedade formal]
```

**Exemplos**

- `values[idx]` -> `0 <= idx < len(values)`
- `item // denom` -> `denom != 0`

**Por que parcial?**

Porque o sistema nao gera uma especificacao completa do programa.  
Ele gera propriedades locais associadas aos achados detectados.

---

# Etapa 6. Instrumentacao

```mermaid
flowchart LR
    A[Codigo original] --> B[Insercao de assert]
    B --> C[Arquivo instrumentado]
```

**O que acontece aqui**

- o pipeline cria uma copia derivada do codigo
- insere `assert` na linha relevante
- salva o arquivo em `artifacts/.../instrumented/`

**Importante**

Esse arquivo existe apenas para verificacao formal.  
Ele nao substitui o codigo original.

---

# Etapa 7. ESBMC

```mermaid
flowchart LR
    A[Arquivo instrumentado] --> B[ESBMC]
    B --> C[Contraexemplo ou sucesso]
```

**O que o ESBMC faz**

- recebe o arquivo instrumentado
- aplica bounded model checking
- busca contraexemplos
- confirma ou refuta a hipotese formal

---

# Etapa 8. Interpretacao do Resultado

```mermaid
flowchart TD
    A[Resultado do ESBMC] --> B{Violacao encontrada?}
    B -- Sim --> C[formally_confirmed_bug]
    B -- Nao --> D[unconfirmed_hypothesis]
    A --> E[Erro de ferramenta]
    E --> F[inconclusive_case]
```

**Leitura**

- se o ESBMC encontra contraexemplo, o bug foi confirmado
- se nao encontra, a hipotese nao foi confirmada
- se a ferramenta falha, o caso e inconclusivo

---

# Exemplo Real do Fluxo

Arquivo analisado:

- `minimal_index_division.py`

Fluxo observado:

1. o pipeline detectou `values[idx]`
2. formalizou `0 <= idx < len(values)`
3. instrumentou o codigo
4. enviou o arquivo ao ESBMC
5. o ESBMC encontrou contraexemplo
6. resultado: `formally_confirmed_bug`

O mesmo aconteceu para:

- `item // denom`

---

# Mapa dos Modulos do Prototipo

```mermaid
flowchart TD
    A[preprocess.py] --> B[llm_analyzer.py]
    B --> C[formalizer.py]
    C --> D[instrumenter.py]
    D --> E[esbmc_runner.py]
    E --> F[report.py]
    F --> G[report.json]
```

**Resumo**

- `preprocess.py` organiza o codigo
- `llm_analyzer.py` detecta e explica
- `formalizer.py` gera propriedades
- `instrumenter.py` cria o arquivo verificavel
- `esbmc_runner.py` chama o ESBMC
- `report.py` consolida a saida

---

# Mensagem Final do Fluxo

**Fluxo completo**

Codigo Python  
-> pre-processamento  
-> analise heuristica por LLM  
-> separacao entre heuristica e verificacao  
-> formalizacao parcial  
-> instrumentacao  
-> ESBMC  
-> classificacao final

**Resumo curto**

LLM detecta e explica.  
ESBMC valida.  
O pipeline separa heuristica de confirmacao formal.
