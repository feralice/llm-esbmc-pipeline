# Dúvidas para reunião com orientador

Pipeline: LLM + ESBMC para detecção de bugs em Python (dissertação mestrado).

---

## 1. O dataset sintético é adequado?

**Contexto:**
Dataset com 70 arquivos Python crafted (não código real de produção):
- 45 bugs: `division_by_zero` (15), `out_of_bounds` (15), `assertion_violation` (15)
- 10 clean (controle negativo)
- 15 code smells (só LLM)

**Por que sintético:**
O frontend Python do ESBMC (v8.3.0) tem suporte parcial — não modela imports externos
(`requests`, `pandas`, etc.). Código real com dependências crasharia ou retornaria
`unsupported_case`. A simplificação manual seria necessária de qualquer forma, então
funções sintéticas isoladas são mais controláveis e reprodutíveis.

Mesma abordagem usada em benchmarks estabelecidos: **Juliet Test Suite (NIST)** e **SV-COMP**
— ambos usam código sintético com ground truth explícito para isolar padrões de defeito
verificáveis.

**Dúvida:**
Isso é suficiente como justificativa metodológica para o paper? Ou precisamos adicionar
pelo menos alguns casos de código real simplificado manualmente?

**Problemas identificados no dataset:**
- Desbalanceamento 4,5:1 (bugs:clean) — métricas podem estar infladas
- Todos os arquivos OOB têm `list[int]` como parâmetro; nenhum `clean` tem lista
  → LLM pode usar presença de lista como atalho, não raciocínio real
- `dz_13.py` e `dz_15.py`: mesma expressão nos dois branches de if/else → detectável
  por linter básico sem verificação formal

---

## 2. LLM sozinha já ajuda? Qual a contribuição real do ESBMC?

**Evidência dos benchmarks V1:**

| Modelo | LLM-only F1 | Híbrido F1 | Redução de ruído | Flow A F1 |
|--------|-------------|------------|-----------------|-----------|
| gpt-4o | 0.88 | **0.95** | 64% | 1.00 |
| gemini-3.1-flash-lite | 0.91 | **0.93** | 33% | 1.00 |
| deepseek-r1-7b | 0.62 | **0.69** | 88% | 1.00 |

**Interpretação:**
- LLM sozinha já detecta bugs com recall alto, mas precision baixa (muitos falsos positivos)
- ESBMC no Flow B elimina falsos positivos da LLM: `noise_reduction` de 33–88%
  dependendo do modelo
- Flow A (ESBMC puro) alcança F1=1.0 para todos os modelos — o dataset é totalmente
  verificável formalmente
- A contribuição do híbrido é **filtrar alucinações da LLM**, não aumentar recall

**Dúvida:**
Se o Flow A (ESBMC puro) já é perfeito no dataset, qual é a contribuição real da LLM
no pipeline híbrido? A justificativa é que em código real o ESBMC sozinho não escala
(sem imports, sem `len()` em listas simbólicas, timeout em funções grandes) — a LLM
triages o que vale verificar formalmente. Isso é suficiente como argumento?

---

## 3. Estou usando o ESBMC corretamente?

**O que o pipeline faz:**
```bash
esbmc --function nome_funcao --assign-param-nondet --unwind 5 arquivo.py
```

- `--function`: entra diretamente na função alvo, sem precisar de `main()`
- `--assign-param-nondet`: todos os parâmetros viram simbólicos automaticamente
  (equivalente a harness manual sem precisar modificar o código)
- `--unwind 5`: analisa loops até 5 iterações

**Como o ESBMC detecta cada tipo de bug:**
- `division_by_zero`: insere `assert denominador != 0` implícito em toda divisão/módulo;
  com `--assign-param-nondet` o solver testa `denominador=0`
- `out_of_bounds`: insere `assert 0 <= index < tamanho_lista` implícito; com parâmetro
  simbólico o solver testa índices fora do range
- `assertion_violation`: verifica `assert` explícitos no código com inputs simbólicos

**Validação:** Flow A com essas flags alcança F1=1.00 (45 TP, 0 FP, 0 FN) nos 3 modelos
testados — confirma que a configuração é correta para o dataset.

**Dúvida:**
`--assign-param-nondet` em parâmetros `list[int]` — o ESBMC cria a lista com tamanho
simbólico (nondet) ou tamanho fixo padrão? Se tamanho fixo, pode haver viés na detecção
de OOB. Onde verificar esse comportamento no código do frontend Python?

---

## 4. Preciso de harness? O que é e quando usar?

**O que é harness:**
Arquivo wrapper que substitui entradas concretas por valores simbólicos e pode impor
pré-condições via `__ESBMC_assume()`:

```python
# Harness manual explícito
x: int = nondet_int()
__ESBMC_assume(x > 0 and x < 100)  # restringe espaço de busca
minha_funcao(x)
```

**No pipeline atual:** não usa harness manual. A flag `--assign-param-nondet` faz o
equivalente automaticamente — todos os parâmetros viram nondet sem modificar o arquivo.

**Quando harness seria necessário:**
- Pré-condições explícitas: testar só inputs válidos (ex: `b > 0` antes de `a / b`)
- Código real com dependências: stub de bibliotecas externas
- Verificação de propriedades mais ricas além de safety (ex: invariantes de classe)

**Dúvida:**
Para o escopo atual (funções curtas, tipadas, sem imports), a ausência de harness é
justificável? Ou o revisor do paper vai questionar que sem `__ESBMC_assume()` o ESBMC
está explorando inputs inválidos que nunca ocorreriam em produção?

---

## Resumo das dúvidas principais

1. Dataset sintético é justificativa metodológica suficiente? (Juliet/SV-COMP como precedente)
2. Com Flow A perfeito, qual argumento usar para justificar o híbrido em código real?
3. Comportamento de `--assign-param-nondet` em `list[int]`: tamanho simbólico ou fixo?
4. Ausência de harness manual é defensável para funções simples e tipadas?
