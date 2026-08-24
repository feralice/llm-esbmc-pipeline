# Leituras recomendadas para a pesquisa Modelos de Linguagem + AST + ESBMC

Levantamento realizado em 23 de agosto de 2026. A lista prioriza artigos originais, páginas de
conferências, documentação oficial e artefatos dos autores. Preprints são identificados para não
serem apresentados como publicação revisada por pares sem confirmação.

## Convenção terminológica

A pesquisa avalia tanto **LLMs** quanto **SLMs**. O documento usa “modelos de linguagem” como termo
geral. A sigla LLM é preservada nos títulos dos artigos e quando a fonte estudou especificamente
modelos grandes. Trabalhos sobre *small language models* são especialmente relevantes para comparar
modelos locais, custo, estabilidade e falsos positivos, mas o porte não deve ser confundido com a
forma de acesso: local/pago e SLM/LLM são dimensões diferentes.

## 1. Cinco leituras prioritárias

### 1.1 Beyond Strict Rules: Assessing the Effectiveness of Large Language Models for Code Smell Detection

- Autores: Saymon Souza, Amanda Santana, Eduardo Figueiredo, Igor Muzetti, João Eduardo Montandon e
  Lionel Briand.
- Ano: 2026.
- Estado encontrado: preprint no arXiv.
- Link: <https://arxiv.org/abs/2601.09873>

É o trabalho mais próximo do fluxo de code smells desta pesquisa. Avalia quatro LLMs em nove smells
e 30 projetos Java. O ground truth humano foi construído com 76 desenvolvedores avaliando 268
candidatos. Os autores observam melhor desempenho em smells estruturalmente simples, como Long
Method, e mais falsos positivos em smells complexos.

Como ajuda esta pesquisa:

- sustenta a separação entre smells quantitativos e contextuais;
- fornece um protocolo de ground truth humano muito mais forte que anotação por uma única pessoa;
- motiva a comparação por categoria, não apenas agregada;
- reforça que a escolha entre precisão e recall muda a melhor estratégia;
- oferece comparação direta com Qwen2.5-Code e DeepSeek-R1;
- ajuda a posicionar a votação e o modelo crítico como tentativas de reduzir falsos positivos.

Pergunta para o orientador: devemos reproduzir parte do protocolo em Python com uma amostra menor e
dois revisores, deixando explícito que não é uma reprodução integral do estudo Java?

### 1.2 ESBMC-Python: A Bounded Model Checker for Python Programs

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

### 1.3 LLM Meets Bounded Model Checking: Neuro-symbolic Loop Invariant Inference

- Autores: Guangyuan Wu, Weining Cao, Yuan Yao, Hengfeng Wei, Taolue Chen e Xiaoxing Ma.
- Evento: ASE 2024.
- DOI: <https://doi.org/10.1145/3691620.3695014>

O trabalho usa uma estratégia de geração e filtragem: a LLM propõe predicados candidatos, enquanto
o mecanismo simbólico verifica sua validade e os recombina. A ideia é importante porque a saída da
LLM não é aceita como verdade.

Como ajuda esta pesquisa:

- oferece precedente direto para arquitetura neuro-simbólica;
- apoia o princípio “LLM propõe, ferramenta formal valida”;
- inspira múltiplas tentativas e aproveitamento de candidatos parciais;
- sugere usar feedback do verificador para refinar propriedades ou harnesses;
- ajuda a defender que o filtro formal é contribuição central, não apenas pós-processamento.

### 1.4 LLM-Generated Invariants for Bounded Model Checking Without Loop Unrolling

- Autores: Muhammad A. A. Pirzada, Giles Reger, Ahmed Bhayat e Lucas C. Cordeiro.
- Evento: ASE 2024; Distinguished Paper Award.
- DOI: <https://doi.org/10.1145/3691620.3695512>
- Página oficial: <https://conf.researchr.org/details/ase-2024/ase-2024-research/112/LLM-Generated-Invariants-for-Bounded-Model-Checking-Without-Loop-Unrolling>
- Artefato: <https://github.com/ibnyusuf/LLM-Generated-Invariants-For-Bounded-Model-Checking>

O trabalho gera invariantes por LLM e utiliza prova formal para verificar as afirmações geradas. É
um precedente muito próximo para a futura geração de harnesses: o modelo produz um artefato formal,
mas uma ferramenta simbólica decide se ele é válido.

Como ajuda esta pesquisa:

- fundamenta a geração de artefatos de verificação por LLM;
- mostra que geração e validação devem ser etapas distintas;
- inspira salvar candidatos rejeitados e iterar com feedback;
- oferece uma comparação conceitual direta por também empregar ESBMC;
- ajuda a delimitar a originalidade: esta pesquisa trabalha com localização de bugs Python,
  casamento AST e síntese de harness, não somente invariantes de laço.

### 1.5 BugsInPy: A Database of Existing Bugs in Python Programs

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

## 2. Leituras para ground truth e code smells

### 2.1 MLCQ: Industry-relevant Code Smell Data Set

- Autores: Lech Madeyski e Tomasz Lewowski.
- Evento: EASE 2020.
- DOI: <https://doi.org/10.1145/3383219.3383264>
- Dataset: <https://zenodo.org/records/3666840>

O MLCQ foi anotado por desenvolvedores com experiência profissional e contém aproximadamente 15 mil
amostras Java. Mesmo não sendo Python, é uma referência importante para construção e documentação
de ground truth humano.

Como usar:

- adaptar o protocolo de anotação, não copiar diretamente seus rótulos para Python;
- registrar experiência dos revisores;
- guardar discordâncias e casos limítrofes;
- comparar smells objetivos e subjetivos;
- considerar uma pequena validação humana independente do dataset desta pesquisa.

### 2.2 SmellDetector: Multi-Label Code Smell Detection and Refactoring with Large Language Models

- Autores: Wenjie Liang et al.
- Evento: IJCNN 2025.
- Versão aberta encontrada: <https://openreview.net/pdf?id=g-LPFWsB9qC>

Propõe detecção multirrótulo de mais de 20 tipos de smells e relaciona detecção com oportunidades de
refatoração. É útil para pensar além da classificação binária por smell.

Cuidados:

- o domínio principal é Java;
- utiliza treinamento/adaptação, diferente da avaliação por prompting desta pesquisa;
- o material do OpenReview deve ser conferido contra a versão final do IJCNN antes da citação final.

### 2.3 Can Small LLMs Detect Defect-Prone Code Smells?

- Autores: Rodrigo Lima, Jairo Souza, Baldoino Fonseca, Leopoldo Teixeira e Márcio Ribeiro.
- Evento: EASE 2026.
- Página oficial: <https://conf.researchr.org/details/ease-2026/ease-2026-ai-models---data/4/Can-Small-LLMs-Detect-Defect-Prone-Code-Smells-An-Empirical-Evaluation-of-8B-30B-Mod>

Avalia modelos pequenos em smells associados a defeitos, incluindo projetos Java e Python. Os
resultados divulgados na página oficial mostram grande variação por tipo: smells estruturais podem
ser detectados melhor que smells de design contextual.

Como ajuda:

- posiciona os modelos locais da pesquisa;
- reforça a necessidade de resultados por categoria;
- conecta smells a risco de defeito sem afirmar que todo smell é bug;
- sugere exemplos e projetos externos para comparação futura.

## 3. Leituras para repetição, votação e crítica

### 3.1 Self-Consistency Improves Chain of Thought Reasoning in Language Models

- Autores: Xuezhi Wang et al.
- Evento: ICLR 2023.
- Artigo oficial: <https://openreview.net/pdf?id=1PL1NIMMrw>

Propõe gerar múltiplos caminhos de raciocínio e selecionar a resposta mais consistente. Não trata
especificamente de bugs ou smells, portanto deve fundamentar a ideia geral de repetição e votação,
não comprovar que ela necessariamente melhorará este pipeline.

Como adaptar:

- executar cada modelo três vezes;
- medir estabilidade por achado;
- agregar por função, categoria e expressão;
- avaliar todos os limites de votação;
- reportar custo adicional e possível perda de recall.

### 3.2 Universal Self-Consistency for Large Language Model Generation

- Autores: Xinyun Chen et al.
- Ano: 2023, preprint.
- Publicação dos autores: <https://deepmind.google/research/publications/50879/>
- Preprint: <https://arxiv.org/abs/2311.17311>

Estende self-consistency a respostas abertas usando uma LLM para selecionar entre candidatos. É mais
próximo da agregação de explicações e harnesses que uma votação de respostas curtas.

Risco para esta pesquisa: se outra LLM decidir qual resposta está correta sem uma regra externa,
ela pode introduzir novo viés. Para expressões e categorias estruturadas, votação determinística é
mais auditável; um árbitro LLM pode ficar como ablação.

## 4. Leituras para geração de propriedades e harnesses

### 4.1 Finding Inductive Loop Invariants using Large Language Models

- Autores: Adharsh Kamath et al.
- Preprint: <https://arxiv.org/abs/2311.07948>

O trabalho gera invariantes com LLM e verifica sua correção usando ferramentas simbólicas. Reforça a
ideia de que plausibilidade textual não basta: o artefato gerado precisa passar por uma validação
formal independente.

### 4.2 Towards Automated Verification of LLM-Synthesized C Programs

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

### 4.3 Automatic Generation of Formal Specification and Verification Annotations Using LLMs and Test Oracles

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

## 5. Como essas fontes formam uma lacuna de pesquisa

Os trabalhos encontrados cobrem partes da proposta:

- LLMs detectando code smells;
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
expressões como “primeiro trabalho”. Com o levantamento atual, é defensável dizer apenas:

> Entre os trabalhos aqui analisados, não foi encontrada uma avaliação que combine localização de
> bugs em Python por LLM, validação de evidência por AST, síntese de harness e confirmação com
> ESBMC-Python usando oráculos ocultos derivados de bugs reais.

## 6. Ordem sugerida de leitura

1. **Beyond Strict Rules** — desenho experimental de smells e ground truth humano.
2. **ESBMC-Python** — capacidade e limitações do backend usado.
3. **LLM Meets Bounded Model Checking** — geração, filtragem e recomposição neuro-simbólica.
4. **LLM-Generated Invariants for BMC** — integração direta entre LLM e ESBMC.
5. **BugsInPy** — procedência, versões e testes de bugs reais.
6. **MLCQ** — protocolo de anotação humana de smells.
7. **Self-Consistency** — repetição e agregação.
8. **Automatic Generation of Formal Specification...** — testes como oráculos para anotações.

## 7. Perguntas bibliográficas para o orientador

1. O artigo **Beyond Strict Rules** deve ser tratado como trabalho relacionado principal para smells,
   mesmo estando como preprint na fonte encontrada?
2. A pesquisa deve reproduzir parte do protocolo humano desse trabalho?
3. Os dois trabalhos do ASE 2024 tornam geração de harness a continuação mais natural do pipeline?
4. Como diferenciar explicitamente harness, invariante, especificação e contraexemplo no texto?
5. BugsInPy e testes originais são suficientes como fonte independente de oráculo?
6. MLCQ pode fundamentar o protocolo de anotação mesmo sendo Java?
7. É necessário realizar uma revisão sistemática para sustentar a alegação de originalidade?
8. Devemos comparar diretamente com o código/artefato de geração de invariantes do ESBMC?
9. Quais trabalhos devem entrar no artigo curto e quais ficam apenas na dissertação?
10. A dissertação deve separar um capítulo de bugs formais e outro de code smells?

## 8. Lacunas de prompt, hints estruturais e métricas (achado da revisão do pipeline, 24/08/2026)

Revisão do código (`research_pipeline/llm/prompts.py`, `ast_utils.py`, `evaluator.py`) encontrou
três lacunas concretas que ainda precisam de leitura antes de virar decisão de projeto. Ficam aqui
como direção de busca, não como leitura fechada.

### 8.1 Few-shot vs. zero-shot prompting

- Brown et al., "Language Models are Few-Shot Learners", NeurIPS 2020.
  Preprint: <https://arxiv.org/abs/2005.14165>

Fundamenta o conceito de few-shot in-context learning, mas é um paper geral, não específico de
detecção de bug/código. O prompt atual (`_build_raw_prompt`) é zero-shot puro, sem nenhum exemplo.

Busca pendente: paper que compare few-shot vs. zero-shot especificamente em detecção de
bug/vulnerabilidade em código (não achado nem verificado nesta sessão).

### 8.2 Tamanho de prompt e degradação de contexto

- Liu et al., "Lost in the Middle: How Language Models Use Long Contexts", TACL 2023.
  Preprint: <https://arxiv.org/abs/2307.03172> — aceito em periódico revisado por pares (confirmado
  nesta sessão).

Mostra que modelos usam pior informação no meio de um prompt longo. Prompt atual do pipeline é
curto (~900-1200 tokens por chamada), então o achado talvez não se aplique diretamente, mas é
referência obrigatória se a dissertação discutir por que o prompt foi mantido enxuto.

### 8.3 Chain-of-thought (relacionado ao bloco de raciocínio do system prompt)

- Wei et al., "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models", 2022.
  Preprint: <https://arxiv.org/abs/2201.11903>

Estado encontrado nesta sessão: preprint arXiv. Não confirmado se a versão final foi aceita em
NeurIPS 2022 — conferir antes de citar como revisado por pares. O bloco "RACIOCÍNIO — pense passo a
passo" do `system_prompt.txt` já implementa essa técnica; falta o texto da dissertação citar a
fonte.

### 8.4 Cobertura de AST por categoria de bug

`ast_utils.py` só extrai três tipos de operação (`division`, `subscript`, `call`), cobrindo bem
apenas 2 das 8 categorias de bug formal (`division_by_zero`, `out_of_bounds`). As outras 6
(`assertion_violation`, `none_misuse`, `type_mismatch`, `invalid_precondition`, `variable_misuse`,
`integer_overflow`) não têm nenhum hint estrutural, nem no modo `ast_hints` de ablação.

Busca pendente: como a literatura de detecção de bug guiada por LLM usa hints estruturais (AST,
CFG, taint) por categoria de bug, não só para os casos "fáceis" de extrair (divisão, índice).
Nenhuma leitura desta lista cobre isso ainda diretamente — candidatos a revisar: trabalhos de
"structured prompting" ou "program-aware prompting" para detecção de vulnerabilidade.

### 8.5 Significância estatística em avaliação com dataset pequeno

- Dietterich, "Approximate Statistical Tests for Comparing Supervised Classification Learning
  Algorithms", Neural Computation, 1998.

**Não verificado nesta sessão** (bloqueio de rate limit ao consultar fonte), citação de memória,
conferir DOI e metadados antes de usar formalmente. Direção de busca: teste de McNemar para
comparar dois classificadores no mesmo conjunto de teste, relevante porque `evaluator.py` hoje
calcula apenas precision/recall/F1 por categoria (`result_tables.py`), sem nenhum teste de
significância entre fluxos (llm-only vs. hybrid vs. esbmc-only) nem correção para dataset pequeno
(~100 itens no V2).
