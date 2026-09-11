# Leituras recomendadas para ajustar o pipeline (Modelos de Linguagem + AST + ESBMC)

Levantamento iniciado em 23 de agosto de 2026. Podado em 1 de setembro de 2026 para focar no que
serve para evoluir o pipeline: localização de bug, síntese de harness, verificação formal,
engenharia de prompt e avaliação. As leituras de code smells (Beyond Strict Rules, MLCQ,
SmellDetector, Can Small LLMs Detect Code Smells), a ordem de leitura antiga e as perguntas
bibliográficas centradas em smells foram para `docs/archive/leituras_code_smells.md`.

A lista prioriza artigos originais, páginas de conferências, documentação oficial e artefatos dos
autores. Preprints são identificados para não serem apresentados como publicação revisada por pares
sem confirmação. Antes de qualquer citação formal, o `citation-verifier` confere título verbatim,
lista de autores, veículo e DOI.

## Sumário de hierarquia (leitura ativa vs. histórico)

Tabela adicionada na revisão de 08/09/2026, só para dar hierarquia; nenhum conteúdo abaixo foi
reescrito ou removido por causa dela. `[NÚCLEO]` é leitura que fundamenta o método atual e fica
prioritária pra reler; `[APOIO]` é contexto útil, leitura secundária; `[HISTÓRICO]` registra decisão
já tomada ou direção já resolvida, não é leitura ativa mas continua documentado. A mesma tag
aparece de novo no início da seção ou subseção correspondente no corpo do texto.

| Seção | Tema | Status |
|---|---|---|
| Convenção terminológica | LLM vs. SLM | [APOIO] |
| 1. Leituras prioritárias | cabeçalho, ver subseções | misto |
| 1.1 | ESBMC-Python (ISSTA 2024) | [NÚCLEO] |
| 1.2 | LLM Meets BMC, invariante neuro-simbólico (ASE 2024) | [NÚCLEO] |
| 1.3 | LLM-Generated Invariants sem loop unrolling (ASE 2024) | [NÚCLEO] |
| 1.4b | Survey of ML for Big Code and Naturalness | [APOIO] |
| 1.4c | Alucinação corrigida por análise de AST determinística | [NÚCLEO] |
| 1.4d | SLMs detectando bug de refatoração | [APOIO] |
| 1.4 | BugsInPy | [NÚCLEO] |
| 2. Repetição, votação e crítica | cabeçalho, mecanismo já implementado na V1 | [HISTÓRICO] |
| 2.1 | Self-Consistency (ICLR 2023) | [HISTÓRICO] |
| 2.2 | Universal Self-Consistency | [HISTÓRICO] |
| 3. Geração de propriedades e harnesses | cabeçalho, ver subseções | misto |
| 3.1 | Inductive Loop Invariants via LLM | [APOIO] |
| 3.2 | Verificação automatizada de programas C sintetizados por LLM | [APOIO] |
| 3.3 | Faria et al., anotação formal validada por oráculo de teste | [NÚCLEO] |
| 4. Como as fontes formam a lacuna (formulação V1) | superada/estendida por 6.5 e 7.6 | [HISTÓRICO] |
| 5. Lacunas de prompt, hints e métricas | cabeçalho, ver subseções | misto |
| 5.1 | Few-shot vs. zero-shot | [APOIO] |
| 5.2 | Lost in the Middle (tamanho de prompt) | [APOIO] |
| 5.3 | Chain-of-thought | [HISTÓRICO] |
| 5.4 | Cobertura de AST por categoria de bug | [APOIO] |
| 5.5 | Significância estatística com dataset pequeno | [APOIO] |
| 6. Leituras para o modo `scan` | direção ativa do V2 | [NÚCLEO] |
| 6.1 a 6.7 | síntese de harness, triagem LLM, CEGAR, SpecGen, limitações ESBMC, ordem de leitura | [NÚCLEO] |
| 7. Estado da literatura para o V2 | revisão mais recente, sustenta a lacuna atual | [NÚCLEO] |
| 7.1 a 7.9 | EVA, FalseCrashReducer, onda 2025, avaliação sem gabarito, mapa e pendências | [NÚCLEO] |
| 8. Trabalhos agênticos de nível de repositório | trabalho relacionado mais recente | [NÚCLEO] |
| 8.1 | RepoAudit | [NÚCLEO] |
| 8.2 | Revelio | [NÚCLEO] |
| 8.3 | IRIS | [NÚCLEO] |
| 8.4 | Sanitizing LLMs in Bug Detection with Data-Flow | [NÚCLEO] |
| 8.5 | Hitchhiker's Guide to Program Analysis, Part II | [APOIO] |
| 8.6 | Estudos e benchmarks úteis para avaliação | [APOIO] |
| 8.7 | Rascunho de contribuição própria | [NÚCLEO] |

Leitura das seções 1 e 2: são as mais antigas do documento. A maior parte da seção 1 continua
núcleo porque fundamenta o backend formal e a procedência do dataset; a seção 2 virou histórico
porque o mecanismo de votação já está implementado na V1, não é mais decisão em aberto.

## Convenção terminológica

**[APOIO]**

A pesquisa avalia tanto **LLMs** quanto **SLMs**. O documento usa "modelos de linguagem" como termo
geral. A sigla LLM é preservada nos títulos dos artigos e quando a fonte estudou especificamente
modelos grandes. Trabalhos sobre *small language models* são especialmente relevantes para comparar
modelos locais, custo, estabilidade e falsos positivos, mas o porte não deve ser confundido com a
forma de acesso: local/pago e SLM/LLM são dimensões diferentes.

## 1. Leituras prioritárias

**[NÚCLEO/APOIO, misto] Núcleo: 1.1, 1.2, 1.3, 1.4c, 1.4 (BugsInPy). Apoio: 1.4b, 1.4d. Ver sumário de hierarquia no topo do arquivo.**

### 1.1 ESBMC-Python: A Bounded Model Checker for Python Programs

**[NÚCLEO]**

- Autores: Bruno Farias, Rafael Menezes, Eddie B. de Lima Filho, Youcheng Sun e Lucas C. Cordeiro.
- Evento: ISSTA 2024.
- DOI: <https://doi.org/10.1145/3650212.3685304>
- Preprint aberto: <https://arxiv.org/abs/2407.03472>
- Documentação atual: <https://esbmc.github.io/docs/python/>

É a fonte principal para explicar arquitetura, anotações de tipo, AST, tradução para representação
intermediária, geração de fórmulas e uso de SMT no ESBMC-Python.

Como ajuda esta pesquisa:

- fundamenta tecnicamente o backend formal;
- ajuda a limitar as alegações à superfície suportada pelo frontend;
- sustenta a distinção entre erro de conversão e contraexemplo formal;
- justifica documentar tipos, unwind, solver, VCC e resultados inconclusivos;
- deve ser a fonte principal para descrever o ESBMC-Python, em vez de explicações secundárias.

### 1.2 LLM Meets Bounded Model Checking: Neuro-symbolic Loop Invariant Inference

**[NÚCLEO]**

- Autores: Guangyuan Wu, Weining Cao, Yuan Yao, Hengfeng Wei, Taolue Chen e Xiaoxing Ma.
- Evento: ASE 2024.
- DOI: <https://doi.org/10.1145/3691620.3695014>

O trabalho usa uma estratégia de geração e filtragem: a LLM propõe predicados candidatos, enquanto
o mecanismo simbólico verifica sua validade e os recombina. A ideia é importante porque a saída da
LLM não é aceita como verdade.

Como ajuda esta pesquisa:

- oferece precedente direto para arquitetura neuro-simbólica;
- apoia o princípio "LLM propõe, ferramenta formal valida";
- inspira múltiplas tentativas e aproveitamento de candidatos parciais;
- sugere usar feedback do verificador para refinar propriedades ou harnesses;
- ajuda a defender que o filtro formal é contribuição central, não apenas pós-processamento.

### 1.3 LLM-Generated Invariants for Bounded Model Checking Without Loop Unrolling

**[NÚCLEO]**

- Autores: Muhammad A. A. Pirzada, Giles Reger, Ahmed Bhayat e Lucas C. Cordeiro.
- Evento: ASE 2024; Distinguished Paper Award.
- DOI: <https://doi.org/10.1145/3691620.3695512>
- Página oficial: <https://conf.researchr.org/details/ase-2024/ase-2024-research/112/LLM-Generated-Invariants-for-Bounded-Model-Checking-Without-Loop-Unrolling>
- Artefato: <https://github.com/ibnyusuf/LLM-Generated-Invariants-For-Bounded-Model-Checking>

O trabalho gera invariantes por LLM e utiliza prova formal para verificar as afirmações geradas. É
um precedente muito próximo para a geração de harnesses: o modelo produz um artefato formal, mas
uma ferramenta simbólica decide se ele é válido.

Como ajuda esta pesquisa:

- fundamenta a geração de artefatos de verificação por LLM;
- mostra que geração e validação devem ser etapas distintas;
- inspira salvar candidatos rejeitados e iterar com feedback;
- oferece uma comparação conceitual direta por também empregar ESBMC;
- ajuda a delimitar a originalidade: esta pesquisa trabalha com localização de bugs Python,
  casamento AST e síntese de harness, não somente invariantes de laço.

### 1.4b A Survey of Machine Learning for Big Code and Naturalness

**[APOIO]**

- Autores: Miltiadis Allamanis, Earl T. Barr, Premkumar T. Devanbu, Charles Sutton.
- Veículo: ACM Computing Surveys, vol. 51, n. 4, artigo 81, 2018.
- DOI: <https://doi.org/10.1145/3212695>
- Preprint aberto: <https://arxiv.org/abs/1709.06182>

Survey de referência sobre representação de código pra aprendizado de máquina e análise de
programa. A seção 4.1.1 ("Syntactic Models") trata especificamente de modelos baseados em AST,
contrastando com representação por token e por grafo; a seção 3 discute por que a AST de uma
função é estruturalmente mais funda e repetitiva que a árvore sintática de um texto em linguagem
natural, o que justifica tratá-la como objeto próprio, não como um "token stream com parênteses".

Como ajuda esta pesquisa:

- fundamenta a escolha de AST (em vez de token ou string) como estrutura de checagem antes de
  aceitar uma alegação da LLM, tanto no grounding do V1 (`ast_utils.py`) quanto na validação de
  harness do V2 (`compat.py`);
- dá vocabulário de literatura pra descrever o que já é intuição de projeto: casar o formato do
  nó (`BinOp`+`Div`, `Subscript`) ou o estado de ligação de um nome (`Store` vs `Load`) contra a
  árvore real, em vez de aceitar o texto reportado pela LLM;
- é leitura de revisão, não de sistema; não resolve a lacuna do §5.4 (cobertura de AST por
  categoria de bug), mas dá a base pra argumentar por que AST é a representação certa antes de
  discutir a cobertura.

### 1.4c Detecting and Correcting Hallucinations in LLM-Generated Code via Deterministic AST Analysis

**[NÚCLEO]**

- Autores: Dipin Khati, Daniel Rodriguez-Cardenas, Paul Pantzer e Denys Poshyvanyk.
- Estado: preprint arXiv 2601.19106, janeiro de 2026.

Precedente quase direto de `compat.py`. O sistema faz o mesmo movimento: parseia o código gerado
pela LLM em AST, valida contra uma base de conhecimento determinística (nomes e parâmetros que
existem de fato) e rejeita ou corrige o que não bate, em vez de aceitar o texto do modelo como
verdade. Em 200 trechos Python: 100% de precisão, 87,6% de recall, 77% dos casos corrigidos
automaticamente sem nova chamada ao modelo.

Como ajuda esta pesquisa:

- é a leitura mais próxima do que `compat.py` faz hoje: distinguir nome ligado (`Store`) de nome
  só usado (`Load`) pra pegar chamada a função nunca definida no harness (achado do smoke test de
  2/09/2026, corrigido no mesmo dia);
- a métrica deles (precisão/recall da detecção de alucinação, taxa de correção automática) é
  modelo direto pra reportar o ganho da checagem de nome indefinido nesta pesquisa;
- diferença a registrar: eles corrigem a alucinação e seguem usando o código; aqui a alucinação
  vira motivo de nova tentativa de síntese (retry com `repair_feedback`), não correção cirúrgica
  do harness.

### 1.4d Evaluating the Effectiveness of Small Language Models in Detecting Refactoring Bugs

**[APOIO]**

- Autores: Rohit Gheyi, Márcio Ribeiro e Jonhnanthan Oliveira.
- Estado: preprint arXiv 2502.18454, fevereiro de 2025.

Compara modelos pequenos (Llama 3.2 3B, Mistral 7B, Gemma, Phi-4 14B) contra modelos proprietários
(o1-mini, o3-mini-high) detectando bug de refatoração em Java e Python. O modelo aberto Phi-4 14B
chega perto do melhor proprietário.

Como ajuda esta pesquisa:

- referência empírica direta pro eixo SLM-local vs LLM-pago que já aparece nos achados do modo
  `scan` (capacidade do modelo importa na qualidade da síntese, ver `makeMappingArray` com
  gpt-4o-mini vs gpt-4o em 01/09/2026);
- dá um segundo dado, fora do próprio pipeline, de que modelo pequeno local pode chegar perto de
  modelo pago em tarefa de detecção de bug bem delimitada, o que sustenta rodar a ablação de custo
  com um modelo local em vez de assumir que só LLM grande serve.

### 1.4 BugsInPy: A Database of Existing Bugs in Python Programs

**[NÚCLEO]**

- Autores: Ratnadira Widyasari et al.
- Evento: ESEC/FSE 2020.
- DOI: <https://doi.org/10.1145/3368089.3417943>
- Artigo: <https://ratnadiraw.github.io/assets/pdf/bugsinpy.pdf>
- Repositório: <https://github.com/soarsmu/BugsInPy>

BugsInPy fornece versões defeituosas e corrigidas de projetos Python e testes que reproduzem os
bugs. É a fonte metodológica principal para a procedência externa do V2.

Como ajuda esta pesquisa:

- sustenta a alegação de que os commits e testes vêm de bugs reais;
- reforça que a versão defeituosa e o patch precisam ser recuperados do histórico;
- permite usar o teste original como fonte independente do oráculo;
- ajuda a distinguir o bug real do harness reduzido criado para o ESBMC;
- exige documentar que a redução ou abstração é desta pesquisa, não do BugsInPy.

## 2. Leituras para repetição, votação e crítica

**[HISTÓRICO] Mecanismo de votação já implementado na V1; a leitura documenta a decisão tomada, não é mais busca em aberto.**

### 2.1 Self-Consistency Improves Chain of Thought Reasoning in Language Models

**[HISTÓRICO]**

- Autores: Xuezhi Wang et al.
- Evento: ICLR 2023.
- Artigo oficial: <https://openreview.net/pdf?id=1PL1NIMMrw>

Propõe gerar múltiplos caminhos de raciocínio e selecionar a resposta mais consistente. Não trata
especificamente de bugs, portanto deve fundamentar a ideia geral de repetição e votação, não
comprovar que ela necessariamente melhorará este pipeline.

Como adaptar:

- executar cada modelo três vezes;
- medir estabilidade por achado;
- agregar por função, categoria e expressão;
- avaliar todos os limites de votação;
- reportar custo adicional e possível perda de recall.

### 2.2 Universal Self-Consistency for Large Language Model Generation

**[HISTÓRICO]**

- Autores: Xinyun Chen et al.
- Ano: 2023, preprint.
- Publicação dos autores: <https://deepmind.google/research/publications/50879/>
- Preprint: <https://arxiv.org/abs/2311.17311>

Estende self-consistency a respostas abertas usando uma LLM para selecionar entre candidatos. É mais
próximo da agregação de explicações e harnesses que uma votação de respostas curtas.

Risco para esta pesquisa: se outra LLM decidir qual resposta está correta sem uma regra externa,
ela pode introduzir novo viés. Para expressões e categorias estruturadas, votação determinística é
mais auditável; um árbitro LLM pode ficar como ablação.

## 3. Leituras para geração de propriedades e harnesses

**[APOIO, com exceção] Apoio: 3.1 e 3.2. Núcleo: 3.3, citada no mapa da seção 7.7.**

### 3.1 Finding Inductive Loop Invariants using Large Language Models

**[APOIO]**

- Autores: Adharsh Kamath et al.
- Preprint: <https://arxiv.org/abs/2311.07948>

O trabalho gera invariantes com LLM e verifica sua correção usando ferramentas simbólicas. Reforça a
ideia de que plausibilidade textual não basta: o artefato gerado precisa passar por uma validação
formal independente.

### 3.2 Towards Automated Verification of LLM-Synthesized C Programs

**[APOIO]**

- Autores: Prasita Mukherjee e Benjamin Delaware.
- Preprint: <https://arxiv.org/abs/2410.14835>

Estuda síntese de programas guiada por especificação e verificação. É menos próximo do domínio
Python, mas ajuda a justificar restrições sintáticas e semânticas sobre código produzido por LLM.

Aplicação possível:

- restringir o formato do harness;
- impedir alteração da função original;
- limitar chamadas e construções permitidas;
- validar mecanicamente antes do ESBMC;
- usar feedback formal para nova tentativa.

### 3.3 Automatic Generation of Formal Specification and Verification Annotations Using LLMs and Test Oracles

**[NÚCLEO]**

- Autores: João Pascoal Faria, Emanuel Trigo, Vinicius Honorato e Rui Abreu.
- Ano: 2026.
- Estado encontrado: preprint.
- Link: <https://arxiv.org/abs/2601.12845>

Investiga geração de precondições, pós-condições, invariantes e auxiliares para Dafny, usando
especificações em linguagem natural e testes como oráculos. É diretamente relevante para a dúvida
sobre utilizar testes reais como fonte independente do harness.

Como ajuda:

- separa geração de anotação e validação pelo verificador;
- usa testes como oráculo, alinhado à proposta para BugsInPy;
- trabalha com reparos iterativos baseados no feedback da ferramenta;
- inspira métricas de sucesso por etapa, não apenas resultado final.

Cuidados: Dafny é uma linguagem orientada à verificação e fornece especificações que normalmente não
existem em um arquivo Python comum. Os resultados não podem ser transferidos diretamente.

## 4. Como essas fontes formam uma lacuna de pesquisa

**[HISTÓRICO] Formulação original da lacuna para o V1 (oráculo derivado de BugsInPy); continua registrada, mas foi estendida pela segunda formulação da seção 6.5 e revisada na 7.6.**

Os trabalhos encontrados cobrem partes da proposta:

- LLMs gerando invariantes ou anotações formais;
- ferramentas formais filtrando candidatos gerados;
- ESBMC verificando programas Python;
- BugsInPy fornecendo bugs e testes reais.

A lacuna potencial desta pesquisa é investigar conjuntamente:

```text
código Python real
       ↓
LLM localiza bug e expressão
       ↓
AST rejeita evidência inexistente ou incompatível
       ↓
LLM sintetiza harness Python compatível com ESBMC
       ↓
ESBMC procura contraexemplo
       ↓
oráculo oculto derivado de teste/commit avalia o harness gerado
```

Essa formulação deve ser confirmada por uma revisão sistemática ou busca estruturada antes de usar
expressões como "primeiro trabalho". Com o levantamento atual, é defensável dizer apenas:

> Entre os trabalhos aqui analisados, não foi encontrada uma avaliação que combine localização de
> bugs em Python por LLM, validação de evidência por AST, síntese de harness e confirmação com
> ESBMC-Python usando oráculos ocultos derivados de bugs reais.

A seção 6 desdobra uma segunda formulação, sem gabarito, para o modo `scan`.

## 5. Lacunas de prompt, hints estruturais e métricas (achado da revisão do pipeline, 24/08/2026)

**[APOIO] Lacunas de prompt e métrica ainda em aberto, exceto 5.3 (chain-of-thought), que já é histórico porque a técnica já está implementada no system prompt.**

Revisão do código (`research_pipeline/llm/prompts.py`, `ast_utils.py`, `evaluator.py`) encontrou
três lacunas concretas que ainda precisam de leitura antes de virar decisão de projeto. Ficam aqui
como direção de busca, não como leitura fechada.

### 5.1 Few-shot vs. zero-shot prompting

**[APOIO]**

- Brown et al., "Language Models are Few-Shot Learners", NeurIPS 2020.
  Preprint: <https://arxiv.org/abs/2005.14165>

Fundamenta o conceito de few-shot in-context learning, mas é um paper geral, não específico de
detecção de bug/código. O prompt atual (`build_user_prompt`) é zero-shot puro, sem nenhum exemplo.

Busca pendente: paper que compare few-shot vs. zero-shot especificamente em detecção de
bug/vulnerabilidade em código (não achado nem verificado nesta sessão).

### 5.2 Tamanho de prompt e degradação de contexto

**[APOIO]**

- Liu et al., "Lost in the Middle: How Language Models Use Long Contexts", TACL 2023.
  Preprint: <https://arxiv.org/abs/2307.03172>: aceito em periódico revisado por pares (confirmado
  nesta sessão).

Mostra que modelos usam pior informação no meio de um prompt longo. Prompt atual do pipeline é
curto (~900-1200 tokens por chamada), então o achado talvez não se aplique diretamente, mas é
referência obrigatória se a dissertação discutir por que o prompt foi mantido enxuto.

### 5.3 Chain-of-thought (relacionado ao bloco de raciocínio do system prompt)

**[HISTÓRICO]**

- Wei et al., "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models", 2022.
  Preprint: <https://arxiv.org/abs/2201.11903>

Estado encontrado nesta sessão: preprint arXiv. Não confirmado se a versão final foi aceita em
NeurIPS 2022, conferir antes de citar como revisado por pares. O bloco "RACIOCÍNIO, pense passo a
passo" do `system_prompt.txt` já implementa essa técnica; falta o texto da dissertação citar a
fonte.

### 5.4 Cobertura de AST por categoria de bug

**[APOIO]**

`ast_utils.py` só extrai três tipos de operação (`division`, `subscript`, `call`), cobrindo bem
apenas 2 das 8 categorias de bug formal (`division_by_zero`, `out_of_bounds`). As outras 6
(`assertion_violation`, `none_misuse`, `type_mismatch`, `invalid_precondition`, `variable_misuse`,
`integer_overflow`) não recebem hints estruturais no prompt.

Busca pendente: como a literatura de detecção de bug guiada por LLM usa hints estruturais (AST,
CFG, taint) por categoria de bug, não só para os casos "fáceis" de extrair (divisão, índice).
Nenhuma leitura desta lista cobre isso ainda diretamente. Candidatos a revisar: trabalhos de
"structured prompting" ou "program-aware prompting" para detecção de vulnerabilidade.

Estado 01/09/2026: a triagem do modo `scan` roda sobre toda função e não recebe hint estrutural
para as 6 categorias sem nó AST próprio. É item de trabalho, não só de leitura.

### 5.5 Significância estatística em avaliação com dataset pequeno

**[APOIO]**

- Dietterich, "Approximate Statistical Tests for Comparing Supervised Classification Learning
  Algorithms", Neural Computation, 1998.

**Não verificado nesta sessão** (bloqueio de rate limit ao consultar fonte), citação de memória,
conferir DOI e metadados antes de usar formalmente. Direção de busca: teste de McNemar para
comparar dois classificadores no mesmo conjunto de teste, relevante porque `evaluator.py` hoje
calcula apenas precision/recall/F1 por categoria (`result_tables.py`), sem nenhum teste de
significância entre fluxos (llm-only vs. hybrid vs. esbmc-only) nem correção para dataset pequeno
(~100 itens no V2).

## 6. Leituras para o modo `scan` (síntese de harness sem ground truth, 31/08/2026)

**[NÚCLEO]**

Este bloco cobre a direção que as seções 1 a 5 não alcançam: apontar o pipeline para um repositório
selvagem, deixar a LLM sintetizar o harness e confirmar com ESBMC, **sem gabarito**. Motivado pela
caça manual de 2026-08-27/28 (issues gluonts#3343 e statsforecast#1221) e pela implementação do
`research_pipeline/scan/` iniciada em 28/08. Títulos e veículos conferidos por busca; metadados
finais (DOI verbatim, lista de autores) ainda a checar antes de citação formal, mesmo padrão das
seções anteriores.

### 6.1 Síntese de harness / driver por LLM

**[NÚCLEO]**

#### OSS-Fuzz-Gen: geração de fuzz driver assistida por LLM (Google)

- Documentação: <https://google.github.io/oss-fuzz/research/llms/target_generation/>
- Repositório: <https://github.com/google/oss-fuzz-gen>
- Estado: infraestrutura de produção, não paper revisado; há relatórios técnicos e posts dos autores.

O sistema recebe uma lista de APIs, pede à LLM um harness de fuzzing, compila, e realimenta o erro
de compilação até o harness rodar; a cada rodada mede cobertura e refina. Já integrou harnesses
novos em projetos reais via OSS-Fuzz.

Por que importa para o modo `scan`:

- é o mesmo formato do passo 3 (LLM produz o artefato de teste, ferramenta decide);
- a limitação que os próprios autores relatam é exatamente a sua: harness genérico gera **crash
  falso-positivo por restrição de entrada errada**. É o `abstraction_gap` com outro nome, e valida
  que `guards.py` e `ablation.py` atacam um problema conhecido;
- o loop compila-erro-refina é o precedente para uma segunda chamada de reparo do harness.

#### PromeFuzz: geração de harness de fuzzing guiada por conhecimento com LLMs

- Evento: ACM CCS 2025.
- DOI a confirmar: <https://doi.org/10.1145/3719027.3765222>

Trabalho revisado por pares sobre a mesma tarefa de síntese de harness, com uma etapa de extração
de "conhecimento" do projeto antes da geração. Serve como âncora acadêmica (não só engenharia) para
posicionar o passo 3, e como comparação de desenho: quanto contexto do projeto a síntese precisa.

### 6.2 LLM filtrando candidatos de análise estática em código real

**[NÚCLEO]**

#### Enhancing Static Analysis for Practical Bug Detection: An LLM-Integrated Approach (LLift)

- Autores: Haonan Li, Yu Hao, Yizhuo Zhai, Zhiyun Qian (a confirmar).
- Veículo: Proceedings of the ACM on Programming Languages (OOPSLA 2024).
- DOI a confirmar: <https://doi.org/10.1145/3649828>

A análise estática gera candidatos, a LLM decide quais valem investigação, com o código relevante
passado sob demanda. Encontrou quatro bugs de uso-antes-de-inicialização inéditos no kernel Linux,
reconhecidos pela comunidade.

Por que importa:

- é o precedente mais próximo da caça selvagem: uma análise estática gera os candidatos, a LLM
  tria, o bug real sai;
- no modo `scan` a triagem da LLM roda sobre todas as funções extraídas, sem um analisador prévio;
- dá base para a alegação de que o filtro formal (aqui, ESBMC no harness) é contribuição central,
  não pós-processamento.

#### A Contemporary Survey of Large Language Model Assisted Program Analysis

- Estado: preprint arXiv, <https://arxiv.org/abs/2502.18474>.

Survey recente que organiza o campo LLM + análise de programa. Uso: mapa de trabalho relacionado
para a introdução, e fonte de tabelas de datasets de bug real (útil também para o §5.5, metodologia
de anotação).

### 6.3 Solidez da abstração e prova espúria

**[NÚCLEO]**

#### Counterexample-Guided Abstraction Refinement (CEGAR)

- Autores: Edmund M. Clarke, Orna Grumberg, Somesh Jha, Yuan Lu, Helmut Veith.
- Veículo: CAV 2000; versão estendida no Journal of the ACM, 2003. Prêmio CAV 2015.
- DOI da versão JACM a confirmar.

Clássico. Uma abstração grosseira demais produz **contraexemplo espúrio**; o laço detecta que ele
não corresponde ao programa real e refina a abstração.

Por que importa (e o paralelo não é literal):

- a super-restrição do harness é o caso dual: uma pré-condição forte demais produz uma **prova
  espúria** (`VERIFICATION SUCCESSFUL` que não vale para o código real);
- `ablation.py` é um refinamento pobre: em vez de refinar a abstração, remove uma hipótese por vez
  e observa se o veredito muda. Vocabulário para o texto: "prova espúria", "abstração forte demais",
  "hipótese não sustentada pelo chamador";
- justifica por que o passo 3 precisa de uma checagem de solidez, e não só do veredito do ESBMC.

### 6.4 Inferência de pré-condição por LLM

**[NÚCLEO]**

#### SpecGen: Automated Generation of Formal Program Specifications via Large Language Models

- Estado: preprint arXiv, <https://arxiv.org/abs/2401.08807>.

Gera especificação formal (pré, pós, invariante) por LLM, com etapa de mutação/seleção para
descartar a que não passa no verificador.

Por que importa:

- `guards.py` hoje extrai pré-condição só por AST (o que a função valida). A rota alternativa é a
  LLM propor a pré-condição e o ESBMC filtrar, como aqui;
- complementa o §3.3 (Faria et al., Dafny): junto, sustentam "gerar anotação é uma etapa, validar
  é outra";
- cuidado: SpecGen mira anotação para verificação, não redução de abstração. O objetivo de
  `guards.py` é o oposto (não deixar a pré-condição esconder o bug), então a técnica entra como
  inspiração de arquitetura, não de meta.

### 6.5 Como o modo `scan` muda a lacuna de pesquisa da seção 4

**[NÚCLEO]**

A formulação do §4 assume oráculo oculto derivado de teste ou commit (estilo BugsInPy, dataset V2
rotulado). O modo `scan` é uma segunda formulação, sem gabarito:

```text
repositório real, pouco auditado
       ↓
toda função extraída por AST vai para a triagem
       ↓
LLM localiza a expressão de risco e a categoria
       ↓
AST rejeita evidência inexistente
       ↓
LLM sintetiza harness escalar; AST restringe a pré-condição ao que a função valida
       ↓
ESBMC procura contraexemplo no harness
       ↓
ablação de hipótese detecta prova espúria (harness super-restrito)
       ↓
métrica sem ground truth: funil + taxa de abstraction_gap por auditoria de amostra
```

Alegação defensável com o levantamento atual:

> Entre os trabalhos aqui analisados, a síntese de harness por LLM aparece para fuzzing (OSS-Fuzz-Gen,
> PromeFuzz) e a triagem de candidatos por LLM aparece para análise estática (LLift), mas não foi
> encontrada uma avaliação que combine localização de bug em Python por LLM, síntese de harness
> compatível com um model checker (ESBMC-Python) e uma checagem de solidez da abstração do harness,
> em código selvagem sem ground truth.

### 6.6 Limitações do ESBMC-Python (não é leitura externa, é fonte primária)

**[NÚCLEO]**

O repositório do ESBMC documenta as limitações do frontend Python, e isso deve alimentar direto o
`synth_prompt.txt` (que construções o harness pode usar) e o texto da dissertação (o que o backend
suporta):

- `~/esbmc/website/content/docs/python/limitations.md` (numpy restrito, strings, dict, exceção,
  concorrência, módulos)
- `~/esbmc/website/content/docs/python/supported-features.md`
- `~/esbmc/src/python-frontend/README.md`
- `~/esbmc/docs/roadmap/python-issues-triage-report-2026-06-02.md`

### 6.7 Ordem de leitura sugerida para esta direção

**[NÚCLEO]**

1. **ESBMC-Python** (§1.1) e o `limitations.md` do repo: o que o backend aceita.
2. **OSS-Fuzz-Gen**: a tarefa de síntese de harness e a falha de restrição de entrada, na prática.
3. **LLift** (§6.2): triagem de candidato por LLM em código real, bug inédito confirmado.
4. **CEGAR** (§6.3): vocabulário de prova espúria e abstração forte demais.
5. **SpecGen** (§6.4) e **Faria et al.** (§3.3): gerar pré-condição vs. validar pré-condição.
6. **PromeFuzz** e o **survey** (§6.1, §6.2): âncoras acadêmicas e mapa de trabalho relacionado.

## 7. Estado da literatura para o V2 (revisão de 1 de setembro de 2026)

**[NÚCLEO]**

Busca dirigida à direção do modo `scan` (código selvagem, síntese de harness por LLM, confirmação
por ESBMC-Python, sem gabarito). Os itens abaixo saíram de busca por palavra-chave nesta data.
Metadados finais (título verbatim, lista de autores, DOI, veículo) precisam passar pelo
`citation-verifier` antes de qualquer citação formal, mesmo padrão das seções 1 a 6.

### 7.1 Três blocos onde a proposta se encaixa

**[NÚCLEO]**

O modo `scan` fica no cruzamento de três linhas que a literatura trata separadas:

- **Modelo de linguagem mais BMC para Python.** Já existe, mas por tradução.
- **Modelo de linguagem triando candidatos de análise estática em código real.** Já existe, com
  onda grande de trabalho em 2025 sobre reduzir falso positivo.
- **Síntese de harness ou driver por modelo de linguagem.** Já existe para fuzzing, e o problema
  de crash falso por harness mal construído já é reconhecido como central.

A combinação dos três, em Python verificado direto e com checagem de solidez do harness, é onde a
contribuição pode estar.

### 7.2 EVA: tradução assistida por modelo de linguagem e BMC de código Python

**[NÚCLEO]**

- Autores prováveis: S. Shivaji, N. Lobakhina, K. Havelund, A. Pinto e L. Cordeiro.
- Veículo encontrado: 3rd AI ISoLA, 2026.
- Cópia local: `artigos_estudo/EVA_LLM_Assisted_Translation_and_BMC_of_Python_Code.md`.

O sistema traduz Python para C com um modelo de linguagem e roda ESBMC no C gerado, com um
orquestrador que coordena análise estática, dinâmica e formal. Avaliação em 23 programas Python
com bug plantado, na faixa de 15 a 50 linhas, laços limitados e estruturas de tamanho estático.
Todos os bugs plantados foram detectados.

Como se relaciona com esta pesquisa:

- é o vizinho mais próximo e vem do mesmo grupo, então precisa entrar como trabalho relacionado
  principal desta direção;
- a diferença de arquitetura é o argumento central: aqui o Python é verificado direto pelo
  ESBMC-Python, sem transpilação, o que evita o risco de a tradução introduzir ou mascarar bug;
- o escopo do EVA é benchmark plantado e curto; o modo `scan` mira função de repositório real,
  sem limite de tamanho definido a priori;
- serve de referência para a discussão sobre quando transpilar para C compensa e quando o
  frontend nativo é preferível.

### 7.3 FalseCrashReducer: reduzir crash falso positivo em geração de fuzz driver

**[NÚCLEO]**

- Autores prováveis: P. C. Amusuo, D. Liu, R. A. Calvo Mendez, J. Metzman, O. Chang e J. C. Davis.
- Estado encontrado: preprint arXiv 2510.02185, outubro de 2025.

Ataca exatamente o problema que aqui se chama `abstraction_gap`: o driver inicializa o estado ou
o input da função de forma inválida e o fuzzer reporta um crash que não acontece no uso real.
Duas estratégias: geração com restrições, que injeta pré-condições de forma proativa, e validação
por contexto, que analisa se o crash reportado é viável olhando os chamadores da função.
Avaliação em 1500 funções, com redução de até 8 por cento nos crashes espúrios e mais de 50 por
cento no total de crashes reportados.

Como se relaciona com esta pesquisa:

- é o estado da arte do problema que `guards.py` e `ablation.py` atacam, e deve ser lido antes de
  escrever o capítulo de síntese;
- o paralelo é quase direto: `guards.py` é a geração com restrições, só que a pré-condição vem do
  AST da função em vez de um agente, e `ablation.py` é uma versão mecânica da validação por
  contexto, removendo uma hipótese por vez para ver se o veredito muda;
- a diferença é o oráculo final: lá é um fuzzer procurando crash, aqui é um model checker
  procurando contraexemplo, o que dá garantia diferente e permite falar em prova espúria, não só
  em crash não reproduzível;
- as métricas deles (redução de reporte espúrio sobre um conjunto grande) são um modelo para a
  métrica de `abstraction_gap` por auditoria de amostra.

### 7.4 Onda de 2025 sobre filtragem de falso positivo por modelo de linguagem

**[NÚCLEO]**

Trabalhos recentes sobre o sub-problema de decidir se um alerta de análise estática é real:

- "Minimizing False Positives in Static Bug Detection via LLM-Enhanced Path Feasibility Analysis",
  preprint arXiv 2506.10322.
- "Sifting the Noise: A Comparative Study of LLM Agents in Vulnerability False Positive Filtering",
  preprint arXiv 2601.22952.
- "The Hitchhiker's Guide to Program Analysis, Part III: Mostly Harmless LLMs", preprint arXiv
  2606.15122.

O que essa onda diz para a pesquisa:

- há consenso de que o modelo de linguagem sozinho não confirma bug e precisa de um filtro
  externo, o que sustenta a tese de que o ESBMC no harness é a contribuição central e não um
  pós-processamento;
- o espaço de "modelo tria, ferramenta confirma" está ficando povoado, então a originalidade
  precisa se apoiar no que é específico daqui: harness escalar sintetizado para um model checker
  e checagem de solidez da abstração;
- vale citar pelo menos um desses para mostrar que a onda foi acompanhada.

### 7.5 Descoberta de bug em escala e avaliação sem gabarito

**[NÚCLEO]**

- "One Bug, Hundreds Behind: LLMs for Large-Scale Bug Discovery", preprint arXiv 2510.14036.
  Conferir se há confirmação formal ou só triagem; se for só triagem, entra como contraste.
- "BugScope: Learn to Detect Bugs Like Human", preprint arXiv 2507.15671. Provável detecção pura,
  sem model checking; citar como contraste de método.
- "Everything You Wanted to Know About LLM-based Vulnerability Detection But Were Afraid to Ask",
  preprint arXiv 2504.13474, cópia local em `artigos_estudo/`. Discute avaliação quando não há
  rótulo de recall: amostragem aleatória, auditoria manual de exploração e alcançabilidade,
  protocolo com revisor humano. É a base metodológica que falta para a métrica-manchete do `scan`.

### 7.6 Lacuna de pesquisa revisada

**[NÚCLEO]**

A formulação do §6.5 continua válida, mas precisa ficar mais precisa depois desta busca:

> A síntese de harness por modelo de linguagem aparece para fuzzing (OSS-Fuzz-Gen, survey de 2025)
> e o problema de falso positivo por harness mal construído já é reconhecido e atacado
> (FalseCrashReducer). A triagem de candidato por modelo de linguagem aparece para análise
> estática (LLift e a onda de 2025). Modelo de linguagem com BMC para Python aparece por
> tradução para C (EVA). Entre os trabalhos analisados, não foi encontrada uma avaliação que
> reúna: verificação de Python direto com um model checker (ESBMC-Python), síntese de harness
> escalar para esse model checker, e uma checagem de solidez da abstração do harness que não
> dependa só do veredito, tudo em código selvagem sem gabarito.

O que é específico desta pesquisa, à luz da revisão:

- verificação nativa de Python, sem a etapa de tradução do EVA;
- `ablation.py` como teste de prova espúria por remoção de hipótese, análogo mecânico da
  validação por contexto do FalseCrashReducer, mas sobre veredito de model checker;
- métrica de `abstraction_gap` por auditoria de amostra, apoiada no protocolo de avaliação sem
  gabarito do survey de vulnerabilidade.

### 7.7 Mapa leitura para decisão de projeto do V2

**[NÚCLEO]**

| Decisão no modo `scan` | Pergunta de banca | Leitura que responde |
|---|---|---|
| Modelo de linguagem sintetiza o harness (passo 3) | já foi feito, por que é difícil | OSS-Fuzz-Gen (§6.1), FalseCrashReducer (§7.3), LLM-Generated Invariants (§1.3) |
| Pré-filtro barato, depois triagem, depois confirmação formal | por que não só análise estática | LLift (§6.2), onda de 2025 (§7.4) |
| `abstraction_gap` e prova espúria por super-restrição | o que um SUCCESSFUL prova de fato | CEGAR (§6.3), FalseCrashReducer (§7.3) |
| `guards.py`, pré-condição por AST em vez de o modelo inventar | por que extrair e não gerar | SpecGen (§6.4), Faria et al. (§3.3), FalseCrashReducer (§7.3) |
| Métrica sem gabarito, funil mais auditoria de amostra | como medir sucesso sem rótulo | survey de vulnerabilidade (§7.5) |
| Síntese estocástica, amostrar k maior que 1 | o harness mudou entre duas execuções | Self-Consistency (§2.1, §2.2) |
| Verificar Python direto, sem transpilar | por que não fazer como o EVA | EVA (§7.2), ESBMC-Python (§1.1) |

### 7.8 Ordem de leitura para fechar a revisão desta direção

**[NÚCLEO]**

1. **EVA** (§7.2): vizinho do grupo, define a diferença de arquitetura.
2. **FalseCrashReducer** (§7.3): estado da arte do `abstraction_gap`.
3. **LLift** (§6.2): precedente de triagem por modelo de linguagem em código real.
4. **ESBMC-Python** (§1.1) e `limitations.md` do repo: superfície do backend.
5. **Everything You Wanted to Know About LLM-based Vulnerability Detection** (§7.5): avaliação
   sem gabarito.
6. **Fuzz Driver Generation Survey de 2025** e **um item da onda de 2025** (§6.1, §7.4): mapa de
   trabalho relacionado.
7. **CEGAR** (§6.3) e **SpecGen** (§6.4): vocabulário de prova espúria e de pré-condição.

### 7.9 Pendências desta revisão

**[NÚCLEO]**

- passar `citation-verifier` em EVA, FalseCrashReducer e nos quatro preprints de 2025 e 2026
  antes de citar;
- ler "One Bug, Hundreds Behind" e decidir se ameaça a lacuna ou entra como contraste;
- os papers de `artigos_estudo/` fora desta lista (PyVeritas, "Vulnerability Detection: from
  Formal Verification to LLMs", os benchmarks de vulnerabilidade) precisam de uma passada para
  ver se entram no trabalho relacionado;
- a seção 6 fala em "issues" para a caça manual; o estado em 1 de setembro é as duas issues
  abertas com PRs da comunidade sem review de mantenedor, ajustar quando houver desfecho.

## 8. Trabalhos agênticos de nível de repositório (levantamento via base ASE, 1 de setembro de 2026)

**[NÚCLEO]**

Fonte: `PurCL/ASE`, base curada de 1.666 artigos sobre engenharia de software com agentes
(ICSE, FSE, ASE, ISSTA, PLDI, OOPSLA, S&P, CCS, NDSS, ACL, ICML, 2023 a 2026), com taxonomia
de tema. Site: <https://chengpeng-wang.github.io/Survey/ase.html>. Arquivo local com abstract
e DOI de cada paper: `data/labeldata/labeldata.json`. Serve para varrer o trabalho relacionado
por rótulo (Bug Detection 249, Program Verification 44, Data-flow Analysis 23, Symbolic
Execution 7, Test Case Generation 118, Program Repair 223). Metadados abaixo saíram dessa base
nesta data; verificar no `citation-verifier` antes de citar.

### 8.1 RepoAudit: agente LLM para auditoria de nível de repositório

**[NÚCLEO]**

- Autores: Jinyao Guo, Chengpeng Wang, Xiangzhe Xu, Zian Su, Xiangyu Zhang (Purdue).
- Veículo encontrado: ICML 2025 (PMLR v267). Repositório: <https://github.com/PurCL/RepoAudit>.
  `[VERIFICAR CITAÇÃO]` veículo sem hedge de "a confirmar" ao contrário do resto da seção 8; checar
  no `citation-verifier` antes de citar formalmente.
- Rótulos ASE: Static Analysis, Bug Detection, Data-flow Analysis, Agent Design, Memory Management.

Arquitetura, lida direto do código:

- **MetaScan** (sem LLM, tree-sitter): varre o repo (`os.walk`, pula `build`/`venv`/`.git`/...),
  extrai toda função e o call graph nos dois sentidos.
- **DFBScan** (o agente, 30 workers em paralelo): um *initiator* por tipo de bug acha os pontos
  de partida por casamento de nó (NPD em Python: todo literal `None` é `source`, todo `x.y` e
  `x[i]` é `sink`). Um *worklist* processa cada `source`: manda **uma função por vez** para o LLM
  (`IntraDataFlowAnalyzer`), lê para onde o valor propaga (ARG / PARA / RET / SINK), segue o call
  graph só nessa direção, com corte de profundidade 3 a 4 e cache de pares `(valor, contexto)`.
  Quando um caminho chega a um `sink`, uma 2ª chamada de LLM (`PathValidator`) decide se o caminho
  inter-procedural é viável; só então escreve o `BugReport`.
- **Chamada de modelo** (`llmtool/LLM_utils.py`): roteamento por substring do nome do modelo
  (`gemini`/`gpt`/`o3-mini`/`claude`/`deepseek`), chave do ambiente, retry `tryCnt < 5`,
  `tiktoken` para custo, temperature 0.0. O modelo nunca executa nada; "simula linha por linha".

Custo relatado: ~100 prompts e US$ 0,57 a 2,54 por projeto de ~250 mil linhas.

Como se relaciona com esta pesquisa:

- é o precedente mais completo da direção "descoberta agêntica no repo": o *initiator* barato
  não decide bug, só ancora a busca; o LLM navega sob demanda; um validador fecha;
- a diferença que sustenta a contribuição: o validador do RepoAudit é **palpite de LLM sobre
  viabilidade**. Aqui o validador seria o **ESBMC-Python sobre um harness escalar sintetizado**,
  que dá contraexemplo formal ou prova limitada, mais a checagem de ablação da abstração;
- RepoAudit mira a tríade de ponteiro (NPD, MLK, UAF), que é forma de C; as 8 categorias formais
  desta pesquisa (divisão por zero, índice, pré-condição, overflow, uso de None, ...) precisam de
  outra definição de `source`/`sink`, ainda não feita na literatura;
- o desenho de par `(initiator, worklist, validador)` e as flags (temperature 0.0, workers
  paralelos, retry no parse) são reaproveitáveis diretamente.

### 8.2 Revelio: detecção agêntica de memory safety em escala de repositório, com custo baixo

**[NÚCLEO]**

- Estado encontrado: preprint arXiv 2606.22263, 2026. DOI: <https://doi.org/10.48550/arXiv.2606.22263>.
- Rótulos ASE: Static Analysis, Bug Detection, Fuzzing, Test Case Generation, Agent Design.

Framework end-to-end para descoberta de vulnerabilidade de memória em repos grandes. Ataca a
alucinação **gerando um artefato executável** (PoC) para confirmar o achado, em vez de confiar no
texto do modelo. É o vizinho mais próximo do argumento "gere algo verificável, não aceite o
texto": Revelio usa PoC dinâmico; esta pesquisa usaria harness mais model checking. A distinção
a registrar: PoC exige compilar e rodar o projeto real; o harness escalar não, e o ESBMC dá
garantia limitada (bounded), não só "rodou e quebrou".

### 8.3 IRIS: análise estática assistida por LLM, repositório inteiro

**[NÚCLEO]**

- Estado encontrado: ICLR 2025. Título de arquivo: "LLM-Assisted Static Analysis for Detecting
  Security Vulnerabilities".
- Rótulos ASE: Static Analysis, Bug Detection, Taint Analysis, Benchmark.

Abordagem neuro-simbólica que combina LLM com análise estática para raciocínio no repositório
inteiro. O ponto que os autores levantam e que vale citar: a ferramenta de análise depende de
especificação rotulada por humano, e o LLM sozinho não faz o raciocínio de caminho; a combinação
é que funciona. Sustenta a tese de que o passo formal (aqui, ESBMC) é a contribuição, não um
enfeite.

### 8.4 Sanitizing LLMs in Bug Detection with Data-Flow

**[NÚCLEO]**

- Estado encontrado: EMNLP Findings 2024. `[VERIFICAR CITAÇÃO]` título e par venue/ano com
  confiança moderada nesta revisão; não achado hedge equivalente ao de outros itens da seção 8,
  conferir verbatim no `citation-verifier` antes de citar.
- Rótulos ASE: Static Analysis, Bug Detection, Data-flow Analysis, Taint Analysis.

Força o LLM a **emitir o caminho de fluxo de dados** em chain-of-thought few-shot e valida esse
caminho contra o programa, para detectar e descartar falso positivo por alucinação. É o mesmo
princípio do `ablation.py` num registro diferente: lá valida-se o caminho que o LLM afirmou; aqui
remove-se cada hipótese do harness e observa-se o veredito. Citar como precedente da ideia
"a saída do LLM tem de ser checada contra o programa, não aceita como verdade".

### 8.5 Hitchhiker's Guide to Program Analysis, Part II (e Part III no §7.4)

**[APOIO]**

- Estado encontrado: preprint arXiv 2025 (Part II); Part III é o 2606.15122 já citado no §7.4.
- Rótulos ASE: Static Analysis, Bug Detection, Empirical Study.

Série que estuda o trade-off precisão/escalabilidade da análise estática e por que a aplicação
ingênua de LLM a análise de programa dá resultado não confiável (modelagem simplificada,
sobre-aproximação de caminho e de restrição de dados). Referência para a seção de motivação:
por que "LLM lê o código e diz se tem bug" não basta.

### 8.6 Estudos e benchmarks úteis para a avaliação

**[APOIO]**

- **Benchmarking LLMs and LLM-based Agents in Practical Vulnerability Detection for Code
  Repositories** (ACL 2025): mostra que detecção real exige análise inter-procedural (bug nasce
  em multi-hop, não em função isolada) e que benchmarks de repositório (ReposVul, VulEval) são
  caros. Base para justificar por que a fonte de candidato fica fora do método medido.
- **How Effective Are They? Exploring LLM Based Fuzz Driver Generation** (ISSTA 2024, DOI
  10.1145/3650212.3680355): estudo empírico da síntese de fuzz driver por LLM. Linha de base de
  comparação para o passo 3.
- **Automatically Inspecting Thousands of Static Bug Warnings with LLM: How Far Are We?**
  (TKDD 2024): triagem de aviso de análise estática por LLM, com número de precisão. Vizinho do
  LLift e da onda do §7.4.
- **CyberGym** (arXiv 2025): 1.507 vulnerabilidades reais com patch, para avaliação de agente em
  escala. Fonte possível de dataset externo.
- **Boosting Static Resource Leak Detection via LLM-based Resource-Oriented Intention Inference**
  (ICSE 2025, DOI 10.1109/ICSE55347.2025.00131): LLM inferindo intenção de recurso para reduzir
  falso negativo e falso positivo de detecção estática. Padrão "LLM completa a especificação que a
  ferramenta não tem".

### 8.7 Onde esta pesquisa fica diferente de todos esses (rascunho de contribuição)

**[NÚCLEO]**

Com o levantamento das seções 6, 7 e 8, a formulação defensável do que é próprio:

> Os validadores de achado nesses trabalhos são: palpite de LLM sobre viabilidade (RepoAudit),
> PoC dinâmico que exige compilar o projeto (Revelio), ou um verificador leve de fluxo de dados
> (Sanitizing, IRIS). Nenhum usa um model checker limitado sobre um harness escalar sintetizado
> para Python, e nenhum faz uma checagem mecânica de que a abstração do harness não esconde o bug
> (ablação de hipótese). As categorias-alvo da literatura de nível de repositório são de memory
> safety (NPD, MLK, UAF); as oito classes de erro de runtime de Python (divisão por zero, índice,
> pré-condição não checada, overflow, uso de None, ...) não têm uma definição de source/sink
> publicada. A avaliação sem gabarito (funil mais auditoria de amostra) é pouco usada: a maioria
> mede contra benchmark de CVE.

Quatro peças candidatas a contribuição, da mais sólida para a mais arriscada:

1. **Validação formal do achado por ESBMC-Python sobre harness sintetizado**, no lugar de palpite
   de LLM ou PoC dinâmico. Dá contraexemplo ou prova limitada.
2. **Checagem de solidez da abstração por ablação de hipótese** (`ablation.py`): prova mecânica de
   que nenhuma `__ESBMC_assume` do harness está mascarando o bug. É o dual do FalseCrashReducer e
   não aparece nos trabalhos de nível de repositório.
3. **Definição de source/sink para as oito classes de erro de runtime de Python**, análoga ao
   extractor de 41 linhas do RepoAudit, mas para aritmética e pré-condição, não ponteiro.
4. **Protocolo de avaliação sem gabarito**: funil (candidatos, harness válidos, confirmados,
   `abstraction_gap`) mais auditoria manual de amostra, com o V1 rotulado como calibração.
