# Limitações Atuais

## 1. ESBMC direto: 0 VCCs em arquivos sem top-level call

**Impacto:** Alto no Flow A (esbmc-direct).

O ESBMC precisa de um ponto de entrada executável para gerar VCCs. Arquivos que contêm apenas definições de função (sem chamada top-level nem `main()`) retornam:

```
Generated 0 VCC(s)
VERIFICATION SUCCESSFUL
```

O pipeline trata isso como `no_vcc_generated` — não como prova de ausência de bug.

**Workaround atual:** O Flow B (LLM + ESBMC) gera um driver simbólico (`__esbmc_driver__`) que torna a função alcançável. Esta é a principal contribuição do pipeline.

**Não confundir com:** `no_violation_found` — que significa verificação real sem violação.

---

## 2. AST: padrões de acesso indexado não-subscript

**Impacto:** Médio — afeta `out_of_bounds` em padrões como `.pop(i)`, `.insert(i, x)`, `.__getitem__(i)`.

O analisador AST detecta `lst[i]` como `ast.Subscript`. Chamadas de método como `lst.pop(i)` geram `ast.Call`, não `ast.Subscript`.

**Solução implementada:** O `_normalize_operation_finding` verifica se a expressão existe como **nó executável no AST** quando o kind não casa. Isso impede que `.pop(i)` seja marcado como alucinação.

**Limitação restante:** O Formalizer não consegue extrair `base` e `index` de `.pop(i)` pela lógica atual de `_extract_subscript_parts`. Achados `.pop(i)` passam pelo Formalizer mas recebem `assertion = "False"` → caem no harness runtime como fallback.

**Para corrigir completamente:** adicionar `_extract_pop_parts()` no Formalizer (ver `docs/architecture.md`).

---

## 3. Parâmetros `str` no driver: valor concreto `"abc"`

**Impacto:** Baixo na prática para o dataset atual, mas limita a generalidade.

O `instrumenter.py` gera drivers com `nondet_int()` para `int` (simbólico), mas usa `"abc"` fixo para `str`. O ESBMC não possui `nondet_str()`.

**Efeito:** Para funções com parâmetro `str`, o ESBMC verifica apenas o comportamento com `"abc"`. Se o bug só ocorre com outras strings específicas, o ESBMC pode não detectar.

**No dataset atual:** `scrapy_18_out_of_bounds.py` usa `str` e `"abc"` acidentalmente ativa o bug (pois `"abc".split(";")` tem só 1 elemento). O resultado é correto, mas não por exploração simbólica completa.

**Solução futura:** modelar o resultado do `.split()` como lista simbólica de comprimento `nondet_int()`.

---

## 4. Harness runtime: não é verificação formal

**Impacto:** Conceitual — precisa ser apresentado corretamente na dissertação.

`runtime_reproduced_by_harness` significa que uma chamada concreta gerada pela LLM levantou a exceção esperada. É evidência de que o bug é atingível, mas não prova formal via BMC.

Diferenças:

| | ESBMC (formal) | Harness (runtime) |
|---|---|---|
| Explora inputs | Simbólico (todos dentro do bound) | Concreto (uma entrada específica) |
| Resultado | Prova ou refutação formal | Evidência de atingibilidade |
| Reprodutível | Determinístico | Depende da entrada gerada pela LLM |
| Peso científico | Alto | Auxiliar |

**Nunca some** `llm_confirmed_by_esbmc` com `runtime_reproduced_by_harness` em métricas de confirmação formal.

---

## 5. ESBMC Python: suporte experimental

**Impacto:** Médio — alguns arquivos retornam `tool_error` ou `unsupported_case`.

O ESBMC 8.0 suporta um subconjunto de Python. Limitações conhecidas:
- Módulos externos (numpy, pandas, torch) → `unsupported_case`
- Alguns type annotations avançados → `tool_error`
- Sem suporte a `async/await` completo
- Sem `nondet_str()`

**Tratamento:** o pipeline diferencia `tool_error` de `violation_found` — um erro do ESBMC nunca vira confirmação de bug.

---

## 6. Harness: sandbox de OS não completo

**Impacto:** Baixo para uso interno de pesquisa.

O harness executa em subprocess isolado mas no mesmo sistema operacional. A validação de segurança via AST bloqueia os padrões perigosos mais óbvios (`import`, `eval`, `exec`, `open`, `while`, dunder methods). Para uso em produção com código não confiável, seria necessário sandbox de OS (Docker, seccomp, etc.).

---

## 7. Casos OOB com propriedade trivialmente falsa

**Impacto:** Baixo nos resultados, mas relevante para interpretação científica.

Alguns casos de `out_of_bounds` usam índices cuja violação é evidente pela própria propriedade gerada.
Exemplos:

- `values[-4]` gera uma obrigação contendo `0 <= -4`, que é sempre falsa.
- `values[len(values)]` gera uma obrigação contendo `len(values) < len(values)`, que é sempre falsa.

Nesses casos o ESBMC confirma uma violação real, mas o contraexemplo pode ser pouco informativo porque
a falha decorre de uma propriedade estaticamente falsa, não de exploração simbólica rica dos inputs.

**Tratamento atual:** manter os casos no dataset como bugs reais e documentar essa limitação.

**Solução futura:** marcar propriedades triviais no `FormalProperty` ou especializar a formalização de
índices constantes/negativos para explicar melhor o tipo de evidência gerada.

---

## 8. Diferença de configuração entre Flow A e Flow B

**Impacto:** Médio para comparação direta entre os fluxos.

O Flow A (`esbmc-direct`) usa `--unwind {bound}`. O Flow B instrumentado usa `--incremental-bmc`.
Isso significa que uma diferença entre Flow A e Flow B pode refletir tanto a metodologia quanto a
configuração do ESBMC.

**Tratamento atual:** os relatórios separam Flow A e Flow B, e o texto experimental deve mencionar a
diferença.

**Solução futura:** parametrizar o Flow B para usar o mesmo bound do Flow A, ou documentar explicitamente
que o Flow B é o fluxo principal e não uma comparação controlada de flags.

---

## 9. `skipped_not_verifiable` agrega achados sem obrigação formal

**Impacto:** Baixo no MVP, mas importante para leitura dos relatórios.

`skipped_not_verifiable` significa que o achado não seguiu para ESBMC porque não havia uma obrigação
formal confiável para aquele item na versão atual do pipeline. Isso pode acontecer em dois grupos:

- smells heurísticos (`complex_conditional`, `long_method`, `many_parameters`), que são intencionalmente
  não formais;
- achados de bug que a LLM marcou como não verificáveis ou que ficaram sem expressão/harness suficiente.

**Tratamento atual:** smells devem aparecer como `heuristic_smell_only` quando categorizados corretamente
pela LLM. `skipped_not_verifiable` fica reservado para itens que não viraram obrigação formal no fluxo.

**Solução futura:** separar explicitamente no relatório os skips por motivo, por exemplo
`skipped_smell`, `skipped_missing_expression` e `skipped_missing_harness`.

---

## 10. Benchmark: dataset ainda pequeno

**Impacto:** Metodológico — os resultados atuais são sanity check técnico, não experimento final.

O dataset V1 atual tem 70 casos: 45 bugs formais, 10 arquivos clean e 15 smells. Ele é suficiente para
sanity check técnico e experimento piloto, mas ainda pequeno para generalização estatística ampla.

---

## Resumo de status por limitação

| Limitação | Status | Prioridade para corrigir |
|---|---|---|
| 0 VCCs em funções sem top-level | Documentado, tratado como `no_vcc_generated` | Baixa — Flow B resolve |
| `.pop(i)` no Formalizer | Parcialmente resolvido (passa pelo harness) | Média |
| `str` simbólico | Documentado no código | Baixa para MVP |
| Harness não é prova formal | Documentado — separado nas classificações | N/A (correto por design) |
| ESBMC Python limitado | Documentado, erros capturados | N/A (limitação da ferramenta) |
| OOB trivialmente falso | Documentado | Baixa |
| Flags Flow A/Flow B diferentes | Documentado | Média |
| `skipped_not_verifiable` agregado | Documentado, smells têm classe própria | Baixa para MVP |
| Dataset pequeno | V1 seed com 70 casos | Alta para experimentos finais |
