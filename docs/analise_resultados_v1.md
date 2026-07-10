# Análise dos Resultados — Benchmark V1

**Dataset:** 70 arquivos Python (45 bugs + 15 smells + 10 clean)  
**Categorias de bugs:** assertion_violation (15), division_by_zero (15), out_of_bounds (15), complex_conditional (5)  
**Categorias de smells:** long_method (5), many_parameters (5), e demais (5)  
**Flows avaliados:** A (ESBMC direto), B (LLM + ESBMC híbrido), C (LLM sozinha)  
**Modelos:** 6 (3 API pagas, 1 API gratuita, 2 locais via Ollama)

---

## 1. Ranking Geral

Ordenado por F1 de bugs no pipeline híbrido (Flow B):

| # | Modelo | Bug F1 (LLM) | Bug F1 (Híbrido) | Smell F1 | Hall% | Tipo |
|---|---|---|---|---|---|---|
| 1 | gpt-5.5 | 0.968 | **0.968** | 0.769 | **0.0%** | API paga |
| 2 | claude-sonnet-4-6 | 0.938 | 0.957 | 0.750 | 2.0% | API paga |
| 3 | gpt-4o | 0.880 | 0.946 | **0.815** | 1.8% | API paga |
| 4 | gemini-3.1-flash-lite | 0.915 | 0.935 | 0.500 | 2.0% | API gratuita |
| 5 | qwen2.5-coder:7b | 0.667 | 0.835 | 0.236 | 24.5% | Local |
| 6 | deepseek-r1:7b | 0.623 | 0.686 | 0.300 | 21.9% | Local |

**ESBMC direto (Flow A): F1=1.000 para todos os modelos** — baseline formal perfeito no dataset atual.

---

## 2. Detecção de Bugs — LLM Sozinha (Flow C)

### 2.1 Precision e Recall

| Modelo | Precision | Recall | F1 | FP | FN |
|---|---|---|---|---|---|
| gpt-5.5 | 0.938 | **1.000** | **0.968** | 3 | 0 |
| claude-sonnet-4-6 | 0.882 | **1.000** | 0.938 | 6 | 0 |
| gemini-3.1-flash-lite | 0.878 | 0.956 | 0.915 | 6 | 2 |
| gpt-4o | 0.800 | 0.978 | 0.880 | 11 | 1 |
| qwen2.5-coder:7b | 0.611 | 0.733 | 0.667 | 21 | 12 |
| deepseek-r1:7b | 0.750 | 0.533 | 0.623 | 8 | 21 |

**gpt-5.5 e claude-sonnet:** recall perfeito (1.0) — não perdem nenhum bug. Diferem apenas na precisão (gpt-5.5 tem menos FP).

**gemini-3.1-flash-lite:** único modelo gratuito no top 4. Perdeu 2 bugs (FN=2) mas mantém desempenho competitivo.

**qwen e deepseek:** padrões opostos de falha. qwen erra por excesso (21 FP — acusa tudo). deepseek erra por omissão (21 FN — deixa passar metade dos bugs).

### 2.2 Desempenho por Categoria de Bug

| Categoria | gpt-5.5 | claude | gemini-3.1 | gpt-4o | qwen | deepseek |
|---|---|---|---|---|---|---|
| assertion_violation | **1.000** | **1.000** | 0.929 | 0.903 | 0.875 | 0.846 |
| division_by_zero | **1.000** | 0.909 | 0.909 | 0.833 | 0.789 | 0.571 |
| out_of_bounds | 0.909 | 0.909 | 0.909 | 0.909 | 0.276 | 0.435 |
| complex_conditional | 0.909 | 0.889 | **0.000** | 0.909 | 0.244 | **0.000** |

**Padrões críticos:**
- `complex_conditional`: gemini-3.1 e deepseek zeram — não detectam condicionais complexas
- `out_of_bounds`: qwen (0.276) e deepseek (0.435) muito abaixo — bugs de acesso a lista são difíceis pra modelos pequenos
- `assertion_violation` e `division_by_zero`: categorias mais simples, todos vão bem (exceto deepseek em division_by_zero)

---

## 3. Pipeline Híbrido — Impacto do ESBMC (Flow B)

O ESBMC filtra FPs do LLM: se o LLM acusa bug mas ESBMC não confirma, o finding é descartado.

| Modelo | FP antes (LLM) | FP depois (Híbrido) | FP removidos | NRR | F1 ganho |
|---|---|---|---|---|---|
| qwen2.5-coder:7b | 21 | 1 | 20 | **95.2%** | +0.168 |
| deepseek-r1:7b | 8 | 1 | 7 | 87.5% | +0.062 |
| gpt-4o | 11 | 4 | 7 | 63.6% | +0.066 |
| claude-sonnet-4-6 | 6 | 4 | 2 | 33.3% | +0.020 |
| gemini-3.1-flash-lite | 6 | 4 | 2 | 33.3% | +0.020 |
| gpt-5.5 | 3 | 3 | 0 | **0.0%** | 0.000 |

**Insight principal:** o ESBMC é mais valioso para modelos com mais FPs. qwen saiu de F1=0.667 para 0.835 com o híbrido — ganho de 17 pontos. Para gpt-5.5, o ESBMC não conseguiu eliminar os 3 FP restantes: esses casos provavelmente envolvem código que está fora do bound de verificação ou com caminhos não alcançáveis.

**FCR (Formal Confirmation Rate):** taxa de hipóteses do LLM que o ESBMC confirma formalmente.

| Modelo | FCR |
|---|---|
| gpt-5.5 | **1.000** |
| claude-sonnet-4-6 | 0.960 |
| gemini-3.1-flash-lite | 0.958 |
| deepseek-r1:7b | 0.960 |
| qwen2.5-coder:7b | 0.850 |
| gpt-4o | 0.870 |

FCR alto não significa ausência de FP — significa que o ESBMC concorda com o LLM quando tenta verificar. Os FP restantes no híbrido são casos onde o ESBMC também não nega a hipótese (inconclusivo dentro do bound).

---

## 4. Detecção de Smells (Flow C)

Smells não têm verificação formal pelo ESBMC — avaliados apenas pelo LLM.

| Modelo | Precision | Recall | F1 |
|---|---|---|---|
| gpt-4o | 0.917 | 0.733 | **0.815** |
| gpt-5.5 | 0.909 | 0.667 | 0.769 |
| claude-sonnet-4-6 | **1.000** | 0.600 | 0.750 |
| gemini-3.1-flash-lite | **1.000** | 0.333 | 0.500 |
| deepseek-r1:7b | 0.500 | 0.214 | 0.300 |
| qwen2.5-coder:7b | 0.134 | **1.000** | 0.236 |

**gpt-4o lidera em smells** — melhor equilíbrio. É o único modelo que perde para o gpt-5.5 em bugs mas supera em smells.

**claude e gemini:** precision=1.0 (não dão alarme falso) mas recall baixo — conservadores demais.

**qwen:** recall=1.0 em smells (encontra todos), mas precision=0.13 — 97 FP. Acusa smell em quase tudo.

### 4.1 Categoria long_method — Problema Sistemático

| Modelo | F1 long_method |
|---|---|
| deepseek-r1:7b | 0.400 |
| gpt-4o | 0.333 |
| qwen2.5-coder:7b | 0.312 |
| gpt-5.5 | **0.000** |
| claude-sonnet-4-6 | **0.000** |
| gemini-3.1-flash-lite | **0.000** |

`long_method` é o smell mais subjetivo: não existe threshold objetivo para "longo demais". Os melhores modelos (gpt-5.5, claude, gemini) simplesmente não reportam — provavelmente conservadores. deepseek detectou 1 de 5 (por acaso?). qwen detectou todos mas com 22 FP. **Nenhum modelo resolveu bem essa categoria.**

---

## 5. Alucinações

| Modelo | Count | Rate | Interpretação |
|---|---|---|---|
| gpt-5.5 | 0 | **0.00%** | Nunca inventou expressão inexistente |
| gpt-4o | 1 | 1.82% | Raro |
| claude-sonnet-4-6 | 1 | 1.96% | Raro |
| gemini-3.1-flash-lite | 1 | 2.04% | Raro |
| deepseek-r1:7b | 7 | 21.88% | Alta — ~1 em 5 findings é alucinação |
| qwen2.5-coder:7b | 13 | 24.53% | Alta — ~1 em 4 findings é alucinação |

Alucinação = LLM referencia expressão (variável, função, linha) que não existe no código analisado. Em produção, isso gera findings completamente inúteis ao desenvolvedor.

---

## 6. Modelos Locais vs API

| Dimensão | API (top 3 média) | Local (média) |
|---|---|---|
| Bug F1 híbrido | **0.957** | 0.761 |
| Smell F1 | **0.778** | 0.268 |
| Hallucination rate | **1.3%** | **23.2%** |
| Custo por rodada | $ (variável) | Grátis |
| Dependência externa | Sim | Não |

**Modelos locais 7b têm limitações estruturais:**
1. Capacidade de raciocínio sobre código menor (menos parâmetros)
2. Dificuldade em seguir formato JSON estruturado → mais alucinações
3. deepseek: otimizado para raciocínio matemático, não análise de código Python
4. qwen: tende a marcar tudo como positivo (recall alto, precision muito baixa)

**Quando usar local:** dado sensível que não pode sair da máquina, volume alto que torna API inviável. Para pesquisa acadêmica com dataset controlado, API é superior.

---

## 7. Síntese e Conclusões

### 7.1 Melhor modelo por objetivo

| Objetivo | Melhor modelo | Justificativa |
|---|---|---|
| Máxima cobertura de bugs | gpt-5.5 ou claude-sonnet | Recall=1.0, F1 híbrido >0.95 |
| Máxima precisão (menos ruído) | gpt-5.5 | Zero alucinações, menor FP |
| Detecção de smells | gpt-4o | Melhor F1 smell (0.815) |
| Custo zero | gemini-3.1-flash-lite | F1=0.935 com API gratuita |
| Sem dependência externa | qwen2.5-coder:7b + híbrido | Aceitável com ESBMC filtrando |

### 7.2 Valor do Pipeline Híbrido

O pipeline híbrido (LLM + ESBMC) justifica-se principalmente para modelos com precisão mais baixa. Para modelos já precisos (gpt-5.5), o ganho é marginal. O ESBMC agrega valor real quando o LLM é ruidoso.

### 7.3 Limitações Identificadas

- **long_method**: nenhum modelo resolve adequadamente — o prompt precisa de threshold explícito (ex: "função com mais de N linhas")
- **complex_conditional**: gemini-3.1 e deepseek zeram — categoria requer raciocínio lógico sobre múltiplas condições
- **Dataset pequeno**: 45 bugs é suficiente para comparação exploratória, mas intervalos de confiança são amplos — resultados devem ser interpretados com cautela

### 7.4 ESBMC como Baseline

F1=1.000 para todos os modelos significa que o ESBMC, quando roda diretamente no dataset, encontra 100% dos bugs sem falso positivo. Isso confirma que o dataset é formalmente verificável e que o ESBMC é um oráculo confiável para este tipo de bug. O desafio do pipeline é aproximar o LLM desse resultado.
