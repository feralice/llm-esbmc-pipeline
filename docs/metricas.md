# Métricas do Pipeline LLM + ESBMC

Pipeline avalia três fluxos em paralelo. Cada métrica tem uma camada e uma pergunta clara.

---

## 0. Tabela rápida de referência

| | Sistema disse BUG | Sistema silenciou |
|---|---|---|
| **Bug real existe** | TP ✓ | FN ✗ |
| **Sem bug** | FP ✗ | TN ✓ |

| Métrica | Fórmula | Usa | Pergunta |
|---|---|---|---|
| **Precision** | TP / (TP + FP) | coluna "disse BUG" | quando acusou, estava certo? |
| **Recall** | TP / (TP + FN) | linha "bug real" | dos bugs reais, quantos achou? |
| **F1** | 2·P·R / (P+R) | P e R | equilíbrio entre os dois |
| **MCC** | fórmula longa | TP+FP+FN+TN | discrimina bem bug vs. limpo? |
| **Accuracy** | (TP+TN) / total | tudo | % de classificações certas |
| **Hallucination Rate** | alucinações / claims verificáveis | FP especial | expressões inventadas que AST rejeitou? |
| **FCR** | confirmados / tentativas ESBMC | Flow B | suspeitas que viraram prova formal? |
| **NRR** | (FP_C − FP_B) / FP_C | FP dos dois flows | ESBMC reduziu quantos % dos FPs? |

---

## 1. Conceitos base (TP / FP / FN / TN)

| Sigla | Nome | Situação |
|---|---|---|
| **TP** | Verdadeiro Positivo | problema existe, pipeline reportou |
| **FP** | Falso Positivo | problema NÃO existe, pipeline reportou mesmo assim |
| **FN** | Falso Negativo | problema existe, pipeline NÃO reportou |
| **TN** | Verdadeiro Negativo | problema NÃO existe, pipeline corretamente silenciou |

> TN só existe na avaliação **por função** (uma função = um voto binário: tem bug / não tem bug).  
> Na avaliação por *finding*, não há TN porque findings só existem quando o pipeline reporta algo.

---

## 2. Métricas padrão de classificação

Aplicadas a bugs **e** smells separadamente.

### Precision
```
Precision = TP / (TP + FP)
```
**Pergunta:** dos problemas reportados, quantos são reais?  
Alto = poucos alarmes falsos.

### Recall
```
Recall = TP / (TP + FN)
```
**Pergunta:** dos problemas reais, quantos foram encontrados?  
Alto = poucos problemas perdidos.

### F1-Score
```
F1 = 2 × Precision × Recall / (Precision + Recall)
```
**Pergunta:** equilíbrio entre precision e recall.  
Útil quando as duas métricas são importantes e o dataset é desbalanceado.

### MCC (Matthews Correlation Coefficient)
```
MCC = (TP × TN - FP × FN) / √((TP+FP)(TP+FN)(TN+FP)(TN+FN))
```
**Pergunta:** o modelo discrimina bem bugs de funções limpas?  
Escala: -1 (perfeito inverso) → 0 (aleatório) → +1 (perfeito).  
Mais estável que F1 em datasets desbalanceados — usa TN, então calculado **por função**.

### Accuracy
```
Accuracy = (TP + TN) / (TP + FP + FN + TN)
```
**Pergunta:** quantas classificações (bug / limpo) estão certas no total?  
Calculada por função. Menos informativa que MCC em datasets desbalanceados.

---

## 3. Os três fluxos avaliados

O pipeline compara três estratégias lado a lado:

| Fluxo | Estratégia | Variáveis no código |
|---|---|---|
| **Flow C — LLM only** | Apenas a LLM decide | `bug_tp/fp/fn`, `bug_func_*` |
| **Flow B — Híbrido** | LLM levanta hipóteses → ESBMC confirma | `hybrid_bug_tp/fp/fn`, `hybrid_bug_func_*` |
| **Flow A — ESBMC only** | ESBMC sem LLM, baseline formal | `esbmc_direct_tp/fp/fn`, `esbmc_direct_func_*` |

Smells **não participam de Flow A ou B** — não são verificáveis formalmente.  
Smells têm Precision / Recall / F1 próprios (`smell_tp/fp/fn`).

---

## 4. Métricas específicas do pipeline

### Taxa de Alucinação (Hallucination Rate)
```
Hallucination Rate = hallucination_count / (bug_tp + bug_fp - ghost_bug_count)
```
**Pergunta:** das suspeitas verificáveis que a LLM emitiu, quantas continham expressões inventadas?

- **Alucinação**: `metadata.expression` aponta linha/variável que **não existe** no código-fonte → AST rejeita antes de chamar o ESBMC.
- **Ghost bug**: LLM diz `verifiable=True` mas o finding type é `suspected_bug + verifiable=False` — tratado como FP, mas **não conta** como alucinação pura (AST não rejeitou a expressão).
- Quanto menor, mais confiáveis as explicações da LLM.

### FCR — Formal Confirmation Rate
```
FCR = llm_confirmed_by_esbmc / (llm_confirmed_by_esbmc + not_confirmed_within_bound + esbmc_inconclusive)
```
**Pergunta:** das suspeitas que chegaram ao ESBMC (Flow B), quantas viraram prova formal?

- Alto = LLM levantou hipóteses boas.
- Baixo = muitas suspeitas fracas ou o ESBMC não conseguiu decidir dentro do bound.

### NRR — Noise Reduction Rate
```
NRR = (bug_fp_flowC - bug_fp_flowB) / bug_fp_flowC
```
**Pergunta:** o ESBMC reduziu quantos % dos FPs que a LLM sozinha produziria?

- 0.0 também é retornado quando Flow C tem zero FPs (indefinido matematicamente).

---

## 5. Contagens auxiliares

| Campo | Significado |
|---|---|
| `hallucination_count` | Findings rejeitados pelo AST (expressão não existe no source) |
| `ghost_bug_count` | `suspected_bug` com `verifiable=False` — FP, mas não alucinação |
| `out_of_scope_count` | Categorias fora das 6 definidas na taxonomia |
| `llm_confirmed_by_esbmc` | Hipóteses da LLM que o ESBMC confirmou (Flow B, match de categoria) |
| `not_confirmed_within_bound` | ESBMC rodou, nenhuma violação encontrada dentro do bound |
| `esbmc_inconclusive` | ESBMC timeout ou erro de ferramenta |
| `llm_missed_esbmc_bug` | Bugs que o Flow A encontrou mas a LLM não apontou |

---

## 6. Bootstrap — Intervalos de Confiança

Todas as métricas numéricas acima ganham intervalo de confiança via **bootstrap percentil**:

- **n = 2000** reamostras com reposição no nível de *caso* (um arquivo = uma unidade)
- **Confiança: 95%** (α = 0.025 em cada cauda)
- Seed fixo = 42 (reprodutível)

Métricas com CI calculado: Precision / Recall / F1 / MCC para Flow A, Flow B, Flow C e Smells.

---

## 7. Resumo visual

```
Função analisada
    │
    ├─ LLM emite findings
    │       │
    │       ├─ verifiable=False (smells) ──────────────── Precision / Recall / F1 (smells)
    │       │
    │       └─ verifiable=True (bug candidates)
    │               │
    │               ├─ AST rejeita expressão ─────────── hallucination_count → Hallucination Rate
    │               │
    │               └─ AST aceita → ESBMC (Flow B)
    │                       │
    │                       ├─ ESBMC confirma ──────────── llm_confirmed_by_esbmc → FCR
    │                       ├─ ESBMC não confirma ──────── not_confirmed_within_bound
    │                       └─ ESBMC inconclusivo ──────── esbmc_inconclusive
    │
    ├─ Flow C (LLM only):    Precision / Recall / F1 / MCC / Accuracy
    ├─ Flow B (Híbrido):     Precision / Recall / F1 / MCC / Accuracy + NRR
    └─ Flow A (ESBMC only):  Precision / Recall / F1 / MCC / Accuracy
```
