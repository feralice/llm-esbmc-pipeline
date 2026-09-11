# Leituras de code smells (arquivado em 1 de setembro de 2026)

Movido de `docs/projeto/leituras_recomendadas.md` quando aquele documento foi podado para focar em
ajuste do pipeline (localização de bug, síntese de harness, verificação formal, prompt,
avaliação). O material aqui continua válido para a parte de code smells da pesquisa, só saiu
da lista principal. As perguntas para o orientador e a ordem de leitura antiga também ficaram
aqui porque eram formuladas em torno de smells.

## Leitura prioritária de smells

### Beyond Strict Rules: Assessing the Effectiveness of Large Language Models for Code Smell Detection

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

## Leituras para ground truth e code smells

### MLCQ: Industry-relevant Code Smell Data Set

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

### SmellDetector: Multi-Label Code Smell Detection and Refactoring with Large Language Models

- Autores: Wenjie Liang et al.
- Evento: IJCNN 2025.
- Versão aberta encontrada: <https://openreview.net/pdf?id=g-LPFWsB9qC>

Propõe detecção multirrótulo de mais de 20 tipos de smells e relaciona detecção com oportunidades de
refatoração. É útil para pensar além da classificação binária por smell.

Cuidados:

- o domínio principal é Java;
- utiliza treinamento/adaptação, diferente da avaliação por prompting desta pesquisa;
- o material do OpenReview deve ser conferido contra a versão final do IJCNN antes da citação final.

### Can Small LLMs Detect Defect-Prone Code Smells?

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

## Ordem de leitura antiga (formulada em torno de smells)

1. **Beyond Strict Rules** — desenho experimental de smells e ground truth humano.
2. **ESBMC-Python** — capacidade e limitações do backend usado.
3. **LLM Meets Bounded Model Checking** — geração, filtragem e recomposição neuro-simbólica.
4. **LLM-Generated Invariants for BMC** — integração direta entre LLM e ESBMC.
5. **BugsInPy** — procedência, versões e testes de bugs reais.
6. **MLCQ** — protocolo de anotação humana de smells.
7. **Self-Consistency** — repetição e agregação.
8. **Automatic Generation of Formal Specification...** — testes como oráculos para anotações.

## Perguntas bibliográficas para o orientador (versão com smells)

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
