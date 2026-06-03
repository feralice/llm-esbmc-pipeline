# Auditoria Técnica e Avaliação de Prontidão — Pipeline LLM + ESBMC V1

Este documento apresenta a auditoria técnica detalhada da **Versão 1 (V1)** do pipeline híbrido de detecção de bugs em Python. A análise foi realizada com base no código-fonte atual do repositório `/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc` e no comportamento das integrações com o ESBMC e o frontend.

---

## 1. Diagnóstico Geral

> [!WARNING]  
> **Diagnóstico: NÃO PRONTO para os experimentos do artigo**  
> 
> Embora o núcleo de instrumentação, o formalizador e o motor de execução estejam estruturalmente corretos e a suíte de testes unitários passe com sucesso, **existem erros metodológicos graves no subsistema de benchmark/avaliação e múltiplos bugs de geração de sintaxe no formalizador** que inviabilizam a geração de resultados válidos para um artigo científico no momento. Além disso, há um problema de configuração e importação na integração com o ESBMC Python.

---

## 2. Pontos Fortes

* **Validação de Segurança Robusta (Runtime Harness)**: O módulo [runtime_harness_validator.py](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/runtime_harness_validator.py) implementa um validador baseado em AST rigoroso e seguro (gating de imports, loops infinitos e chamadas perigosas), impedindo execução de código arbitrário malicioso.
* **Mapeamento de Falhas Fáceis (AST Gating)**: A estratégia de validação AST pós-LLM no [findings.py](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/llm/findings.py) é excelente para limpar falsos positivos evidentes da LLM (alucinações de operações inexistentes no código).
* **Modularidade do Formalizador e Instrumentador**: O fluxo de tradução do achado da LLM para propriedades formais e a injeção do driver simbólico (`__esbmc_driver__`) em [instrumenter.py](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/instrumenter.py) estão muito bem estruturados e isolados.
* **Visualização Fluida**: O frontend [index.html](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/frontend/index.html) é leve, modular, lê diretamente os JSONs estruturados do pipeline e do benchmark e facilita a análise manual das classificações sem alterar os dados brutos.

---

## 3. Problemas Críticos (Bloqueadores para o Artigo)

### CRÍTICO 1: O modo Benchmark ignora a verificação formal do ESBMC (Divergência Metodológica)
* **Onde**: [evaluator.py:L163-233](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/evaluator.py#L163-233) (`evaluate_file`)
* **Descrição**: A função de avaliação principal usada no comando `--mode benchmark` executa apenas a análise do LLM + AST validation contra o Ground Truth. Ela **não** executa a etapa de instrumentação e execução do ESBMC para o Flow B.
* **Impacto**: As métricas de *Precision*, *Recall* e *F1* calculadas no benchmark refletem o desempenho do **LLM puro (com filtro AST)**, e não do **pipeline híbrido LLM+ESBMC**. Em um artigo científico, isso invalida a tese de que o ESBMC atua como filtro de falsos positivos da LLM, pois o benchmark reportado não usa o ESBMC na classificação final dos achados do Flow B.

### CRÍTICO 2: Bug de Sintaxe no Formalizador de Slices (Índices Fora de Limite)
* **Onde**: [formalizer.py:L80-92](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/formalizer.py#L80-92) (`_formalize_out_of_bounds` e `_extract_subscript_parts`)
* **Descrição**: A função `_extract_subscript_parts` não trata nós de fatiamento (`ast.Slice`). Se a LLM apontar um acesso por fatia (ex: `lst[1:3]`), ela irá descompilar a fatia diretamente para string (`"1:3"`). O formalizador então gera a asserção `assert (0 <= (1:3)) and ((1:3) < len(lst))`.
* **Impacto**: A expressão gerada `(1:3)` é uma sintaxe inválida no Python e causa erro imediato de parser (`tool_error`) no ESBMC, impedindo a verificação de qualquer código contendo fatiamentos.

### CRÍTICO 3: Bug de Propagação de Fatias em Assunções (Reachability Assumptions)
* **Onde**: [formalizer.py:L177-184](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/formalizer.py#L177-184) (`_build_reachability_assumptions`)
* **Descrição**: Mesmo ao analisar um bug de outra categoria (ex: `division_by_zero`), o formalizador gera assunções de alcançabilidade para garantir que os acessos a coleções no método não quebrem antes. Se a função contiver qualquer fatiamento (ex: `lst[1:3]`), a assunção inválida `__ESBMC_assume((0 <= (1:3)) ...)` será inserida no arquivo instrumentado.
* **Impacto**: A presença de um fatiamento comum inviabiliza a análise de **qualquer outra categoria de bug** dentro da mesma função devido ao erro de sintaxe injetado.

### CRÍTICO 4: Bug de Quebra em Asserções com Múltiplos Parâmetros
* **Onde**: [formalizer.py:L125-130](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/formalizer.py#L125-130) (`_assertion_property_from_expression`)
* **Descrição**: Para remover a mensagem opcional do assert, a função realiza um split simples por vírgula: `expression[len("assert ") :].split(",", 1)[0]`.
* **Impacto**: Se a condição do assert contiver uma chamada de função com múltiplos parâmetros (ex: `assert max(a, b) > 0, "erro"`), o código será cortado na primeira vírgula, gerando a asserção inválida `assert max(a`, gerando erro de sintaxe (`tool_error`).

### CRÍTICO 5: Omissão de Falsos Negativos do Baseline Direct no Benchmark
* **Onde**: [evaluator.py:L226-229](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/evaluator.py#L226-229)
* **Descrição**: Ao calcular as estatísticas de baseline do ESBMC Direto, falhas do baseline (como `no_vcc_generated`, `timeout`, `tool_error`, `unsupported_case`) em arquivos que continham bugs reais **não** são incrementadas como False Negatives (`esbmc_direct_fn`).
* **Impacto**: A métrica de *Recall* e *F1* do baseline direto fica inflada de forma irrealista, mascarando as limitações do ESBMC direto na comparação de tabelas do artigo.

### CRÍTICO 6: Penalização Incorreta em Casos Limpos (Clean Code Penalty Bug)
* **Onde**: [evaluator.py:L190-210](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/evaluator.py#L190-210)
* **Descrição**: Quando o avaliador processa um arquivo classificado como `clean` no Ground Truth (por exemplo, `clean_math.py`), o Ground Truth especifica `verifiable: false`. O avaliador coloca esse caso em `exp_smells`. Se a LLM se comportar perfeitamente e não encontrar nenhum smell (`smells = []`), a função `_match_with_categories` procurará a categoria `"clean"` na lista de smells gerados. Como a lista está vazia, o avaliador registra um **False Negative (FN)**.
* **Impacto**: Arquivos de código limpos aumentam artificialmente o número de falsos negativos (`smell_fn`), derrubando incorretamente a métrica de *Recall* e *F1* de smells de um modelo que se comportou perfeitamente.

### CRÍTICO 7: Falha de Configuração do PYTHONPATH para o ESBMC
* **Onde**: [esbmc_runner.py:L168-174](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/esbmc_runner.py#L168-174)
* **Descrição**: O runner do ESBMC injeta os pacotes do ambiente virtual no `PYTHONPATH` do subprocesso, mas não fornece uma forma de configurar ou injetar o diretório do repositório clonado do ESBMC Python (`esbmc-python-cpp-main`).
* **Impacto**: Sem configurar manualmente o `PYTHONPATH` na shell antes de rodar, toda execução do ESBMC instrumentado falha silenciosamente com a mensagem `ERROR: Module 'esbmc' not found` no log do ESBMC, classificando incorretamente todos os casos de verificação como `inconclusive`.

---

## 4. Problemas Médios

### MÉDIO 1: Estratégia de correspondência fraca (Weak Matching) no Benchmark
* **Onde**: [evaluator.py:L135-161](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/evaluator.py#L135-161) (`_match_with_categories`)
* **Descrição**: O matching entre os achados gerados e os esperados no Ground Truth é feito **apenas pela categoria** (ex: `division_by_zero`). O avaliador ignora a função e a linha do achado.
* **Impacto**: Se o LLM alucinar uma divisão por zero em uma função `func_B`, mas o arquivo continha uma divisão por zero real em `func_A`, o validador marcará o achado como **True Positive (TP)**. Isso infla artificialmente os resultados e compromete o rigor do benchmark científico.

### MÉDIO 2: Inconsistência nos Metadados de Linha do Ground Truth
* **Onde**: Arquivos JSON de Ground Truth (ex: `assertion_violation.json`)
* **Descrição**: O Ground Truth armazena o número da linha **relativa** à função na chave `"line"`. No entanto, no pipeline, a chave `"line"` é tratada como a linha **absoluta** no arquivo fonte original. O preprocessador enriquece e ajusta isso dinamicamente no pipeline de execução, mas no benchmark isso gera confusão estrutural.

### MÉDIO 3: Limitação de Tipagem no Instrumentador
* **Onde**: [instrumenter.py:L73-101](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/instrumenter.py#L73-101) (`_build_symbolic_value`)
* **Descrição**: Parâmetros do tipo `str` são inicializados de forma fixa como `"abc"`. Coleções `list[int]` e `list[float]` são geradas com tamanho estático 3.
* **Impacto**: Bugs que só se manifestam com strings vazias, de tamanhos específicos, ou listas de tamanhos variados não serão descobertos pelo ESBMC. Essa limitação precisa ser explicitada na seção de "Ameaças à Validade" (Threats to Validity) do artigo.

---

## 5. Problemas Menores / Detalhes de Código

* **Efeito colateral do CRLF no .env**: O arquivo `.env` gerado com quebras de linha Windows (`\r\n`) faz com que as chaves de API sejam lidas com `\r` no final, quebrando chamadas HTTP de bibliotecas internas (`http.client` lança `ValueError: Invalid header value`).
* **Dificuldade de execução unificada**: O benchmark não aceita o diretório raiz `ground_truths/` diretamente porque faz uma busca não-recursiva por JSONs (`glob("*.json")`). É necessário executar apontando para subpastas ou alterar a busca para recursiva (`rglob`).
* **Mapeamento parcial de IndexError em Preprocess**: Operações como `.pop(i)` ou `.insert(i)` não são marcadas como `subscript` no preprocessador do AST, sendo mapeadas como `suspected_bug` apenas via fallback dinâmico (`ast_unrecognized = True`).

---

## 6. Avaliação da Integração com o ESBMC

1. **Definição de `nondet_float()` ausente em C++**: 
   No clone `esbmc-python-cpp-main/esbmc.py` e nos arquivos `.hpp` do projeto de pesquisa do ESBMC Python, **não existe definição para `nondet_float`** (apenas para `nondet_int`, `nondet_uint64` e `nondet_bool`).
   * *O que acontece*: O ESBMC no pipeline de execução consegue fazer a tradução interna da instrução (o frontend de compilador do ESBMC aceita a declaração do tipo), mas o arquivo instrumentado `.py` gerado falha ao ser rodado via interpretador Python padrão em testes unitários devido a um `ImportError`.
2. **Utilização correta dos recursos**: A escolha de flags do ESBMC em [formalizer.py](file:///mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/research_pipeline/formalizer.py) (ex: `--no-bounds-check` para divisões e `--no-div-by-zero-check` para bounds) faz sentido do ponto de vista do ESBMC para focar a análise e acelerar o solver de restrições.
3. **Limitação de bound fixo**: O uso de `--unwind 5` em Flow A e `--incremental-bmc` em Flow B é razoável para V1. Porém, a ausência de um timeout global tratado de forma limpa por arquivo pode travar o pipeline sob loops complexos do ESBMC.

---

## 7. Avaliação do Frontend

* **Leitura correta dos JSONs**: O frontend lê perfeitamente os esquemas gerados. O suporte a múltiplos arquivos de benchmark via drag-and-drop permite uma comparação direta de modelos muito rica.
* **Lógica de classificação**: A lógica de visualização preserva estritamente as classificações do backend. O visualizador é puramente passivo e informativo, o que é ideal para manter a integridade dos dados brutos de auditoria.
* **Pontos de Melhoria Estética**: O visualizador adota estilos de design limpos e minimalistas, mas pode ser enriquecido para destacar de forma mais visual a diferença entre achados puramente de LLM (smells) e achados validados formalmente (bugs ESBMC).

---

## 8. Avaliação dos Datasets

* A distribuição de **26 exemplos** é pequena para um artigo internacional de alto impacto, mas é suficiente como prova de conceito (V1) e validação de pipeline.
* A separação entre bugs formais reais (BugsInPy adaptados) e code smells sintáticos está correta. A inclusão de 2 casos de controle (`clean`) é metodologicamente essencial.

---

## 9. Avaliação dos Ground Truths

* O mapeamento no Ground Truth é claro e direto.
* **Recomendação**: Corrigir a chave `"line"` para refletir o número absoluto da linha no código, e introduzir uma nova chave `"relative_line"` para que a compatibilidade com o analisador do pipeline seja declarativa e livre de ambiguidades.

---

## 10. Avaliação do Benchmark

* Além dos problemas críticos listados (Críticos 1 e 2), o cálculo das métricas de alucinação e taxas globais está correto e bem documentado em `evaluator.py`.

---

## 11. Avaliação da Arquitetura

* A arquitetura planejada está bem refletida nas classes e módulos de `/research_pipeline`.
* O desvio entre o planejamento e o código implementado reside na ausência do cálculo das métricas do híbrido (Flow B + ESBMC) no benchmark automatizado.

---

## 12. Avaliação de Clean Code

* **Nomenclatura**: A nomenclatura de funções e variáveis é consistente e legível (ex: `coerce_findings_payload`, `_guard_covers_operation`).
* **Responsabilidades misturadas**: A classe `EvalCounts` mistura acumulação global de estatísticas e mapeamentos por categoria, mas não é grave.
* **Duplicação**: Baixa duplicação de lógica de execução. O reaproveitamento da chamada do subprocesso ESBMC entre Flow A e Flow B é bem implementado.

---

## 13. Checklist Final antes dos Experimentos

- [ ] Instalar o pacote stubs/wrapper `esbmc` no `.venv` do projeto ou adicionar `/mnt/c/Users/ferna/Documents/mestrado/pesquisa/esbmc-python-cpp-main` de forma persistente no `PYTHONPATH` do executor.
- [ ] Corrigir o loop de avaliação do benchmark para rodar a instrumentação e execução do ESBMC em achados `verifiable` do Flow B antes de comparar com o Ground Truth.
- [ ] Ajustar o validador de clean code em `evaluator.py` para não registrar falsos negativos quando a categoria de Ground Truth for `"clean"`.
- [ ] Corrigir no formalizador a geração de propriedades para ignorar/rejeitar fatias (`ast.Slice`) na detecção de bounds.
- [ ] Corrigir o split de asserções em `formalizer.py` para realizar análise sintática da árvore AST ao invés de split por vírgula.
- [ ] Atualizar a computação de False Negatives do baseline no benchmark para incluir falhas de processamento.
- [ ] Rodar uma verificação completa de ponta a ponta dos 26 arquivos de teste para gerar um `full_report.json` de referência.

---

## 14. O que precisa ser corrigido OBRIGATORIAMENTE antes de rodar os benchmarks finais

1. **Correção do Benchmark (`evaluator.py`)**: Integrar a chamada da verificação do ESBMC no loop do benchmark. Somente achados marcados pela LLM como `verifiable` **e** que resultem em `violation_found` pelo ESBMC devem ser contabilizados como True Positives da trilha de bugs do pipeline.
2. **Correção das Falhas do Baseline (`evaluator.py`)**: Computar falhas de ferramentas (timeout, tool_error, etc.) em casos de bugs como False Negatives do baseline direto.
3. **Ajuste do filtro de Clean Cases em `evaluator.py`**: Excluir a categoria `"clean"` de ser inserida na lista de `exp_smells` em `evaluate_file`.
4. **Resolução de Slices no Formalizador (`formalizer.py`)**: Validar se o nó do índice é `ast.Slice` e não formalizar ou ajustar para retornar `False` seguro.
5. **Resolução de Asserções com Vírgula em `formalizer.py`**: Parsear a expressão usando `ast` para isolar a condição da asserção de forma robusta.
6. **Configuração do `PYTHONPATH` no script de execução**: Ajustar o script para que o subprocesso encontre o arquivo `esbmc.py` do clone sem erros de importação.
