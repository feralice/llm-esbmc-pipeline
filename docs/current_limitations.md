# Limitações Atuais

## 1. ESBMC precisa de ponto de entrada simbólico

**Impacto:** Resolvido no Flow A/B atuais; documentado como motivo do uso de `--function`.

O ESBMC precisa de um ponto de entrada executável para gerar VCCs. Por isso, os fluxos principais não rodam mais o arquivo apenas em nível de módulo. Eles usam:

- **Flow A:** ESBMC-only com `--function <funcao>` para cada função detectada pelo AST.
- **Flow B:** LLM escolhe achados verificáveis e ESBMC confirma com `--function <funcao>`.
- **Flow C:** LLM-only, sem chamada ao ESBMC.

O status legado `no_vcc_generated` continua tratado como não-prova caso algum helper experimental rode ESBMC em nível de módulo, mas não é o baseline principal da V1.

---

## 2. AST: padrões de acesso indexado não-subscript

**Impacto:** Médio — afeta `out_of_bounds` em padrões como `.pop(i)`, `.insert(i, x)`, `.__getitem__(i)`.

O analisador AST detecta `lst[i]` como `ast.Subscript`. Chamadas de método como `lst.pop(i)` geram `ast.Call`, não `ast.Subscript`.

**Solução implementada:** O `_normalize_operation_finding` verifica se a expressão existe como **nó executável no AST** quando o kind não casa. Isso impede que `.pop(i)` seja marcado como alucinação.

**Limitação restante:** o ESBMC pode não tratar todos os padrões Python dinâmicos com a mesma precisão. A validação AST evita alucinação, mas o resultado formal ainda depende do suporte do frontend Python do ESBMC.

**Para corrigir completamente:** ampliar a categorização de padrões AST e documentar quais operações o frontend Python do ESBMC cobre de forma confiável.

---

## 3. Parâmetros simbólicos dependem do suporte do ESBMC Python

**Impacto:** Baixo na prática para o dataset atual, mas limita a generalidade.

No Flow B atual, o ESBMC recebe `--function <funcao>` e cria o ponto de entrada simbólico a partir da própria função. A qualidade da exploração depende do suporte do frontend Python do ESBMC para os tipos usados.

**Efeito:** tipos simples como `int` tendem a funcionar melhor. Tipos como `str`, listas e chamadas de biblioteca podem depender de modelagem parcial do frontend.

**Solução futura:** registrar por categoria quais tipos de parâmetro e operações são suportados de forma estável pelo ESBMC Python.

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

**Solução futura:** marcar no relatório quando a violação decorre de índice constante/trivial para explicar melhor o tipo de evidência gerada.

---

## 8. Diferença entre Flow A e Flow B

**Impacto:** Médio para interpretação experimental.

Flow A e Flow B usam `--function <funcao>` e o mesmo `--unwind {bound}`. A diferença é a origem da função/candidato:

- Flow A varre funções detectadas pelo AST, sem hipótese da LLM.
- Flow B verifica apenas achados que a LLM propôs e que a validação AST aceitou.

**Tratamento atual:** os relatórios separam Flow A, Flow B e Flow C para comparar ESBMC-only, LLM+ESBMC e LLM-only.

---

## 9. `skipped_not_verifiable` agrega achados sem obrigação formal

**Impacto:** Baixo no MVP, mas importante para leitura dos relatórios.

`skipped_not_verifiable` significa que o achado não seguiu para confirmação formal no Flow B atual. Isso pode acontecer em dois grupos:

- smells heurísticos (`complex_conditional`, `long_method`, `many_parameters`), que são intencionalmente
  não formais;
- achados de bug que a LLM marcou como não verificáveis, ficaram fora do escopo ou não puderam ser enviados ao ESBMC.

**Tratamento atual:** smells devem aparecer como `heuristic_smell_only` quando categorizados corretamente
pela LLM. `skipped_not_verifiable` fica reservado para itens que não viraram confirmação formal no fluxo.

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
| Ponto de entrada simbólico | Resolvido com `--function` em Flow A/B | Baixa |
| `.pop(i)` e padrões dinâmicos | Dependem do suporte do ESBMC Python | Média |
| Tipos simbólicos Python | Documentado | Baixa para MVP |
| Harness não é prova formal | Documentado — separado nas classificações | N/A (correto por design) |
| ESBMC Python limitado | Documentado, erros capturados | N/A (limitação da ferramenta) |
| OOB trivialmente falso | Documentado | Baixa |
| Diferença Flow A/Flow B | Documentada | Média |
| `skipped_not_verifiable` agregado | Documentado, smells têm classe própria | Baixa para MVP |
| Dataset pequeno | V1 seed com 70 casos | Alta para experimentos finais |
