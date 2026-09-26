# Log de literatura (loop autônomo)

Um item por artigo lido em função de um ciclo do loop `/loop 1h`. Formato fixo por item,
preenchido só depois de conferir a fonte primária (nunca por resumo de terceiros). Metadados
formais (DOI, autor verbatim) ainda precisam passar pelo mesmo processo de verificação usado no
`docs/projeto/leituras_recomendadas.md` antes de qualquer citação fora deste log.

## Modelo de entrada

```
### <título> (<ano>)

- Referência: <autores completos, veículo>
- Link: <url>
- Problema tratado: <1-2 frases>
- Técnica proposta: <1-2 frases>
- Benchmark: <o que os autores mediram, em cima de quê>
- Métricas: <as métricas que os autores reportaram>
- Resultado principal: <número(s) central(is) do paper>
- Hipótese aplicável aqui: <como isso viraria uma mudança concreta no pipeline>
- Diferença benchmark deles vs dataset daqui: <honesto sobre o que não bate>
- Limitação da comparação: <o que a comparação não prova>
```

---

### Type-Constrained Code Generation with Language Models (2025)

- Referência: Niels Mündler, Jingxuan He, Hao Wang, Koushik Sen, Dawn Song, Martin T. Vechev.
  Proceedings of the ACM on Programming Languages, vol. 9, issue PLDI. PLDI 2025.
- Link: <https://doi.org/10.1145/3729274>
- Problema tratado: LLM gera código que não compila porque o próximo token não modela regras
  formais de tipo da linguagem; em TypeScript, ~94% dos erros de compilação são violação de tipo,
  não de sintaxe.
- Técnica proposta: decodificação restrita por tipo (`type-constrained decoding`), usando
  autômato de prefixo e inferência de tipo pra só permitir token que mantém o código bem tipado.
- Benchmark: HumanEval e MBPP, tarefas de síntese, tradução e reparo de código, vários modelos
  incluindo modelos abertos de 30B+.
- Métricas: taxa de erro de compilação, correção funcional.
- Resultado principal: reduz erro de compilação em mais da metade, aumenta correção funcional.
- Hipótese aplicável aqui: **inversa, não direta**. O problema deles é código mal tipado; o
  problema achado no EXP-02 (`docs/v2/experiment_log.md`) é código **bem** tipado que ainda assim
  não prova nada, porque o tipo declarado do parâmetro (`nondet_bool()`) já elimina por
  construção a condição que o assert testa (`isinstance(param, bool)` é sempre verdade se `param`
  só pode ser `bool`). O paralelo que vale: os dois mostram que o sistema de tipos da linguagem
  interage com a geração da LLM de um jeito que o prompt sozinho não controla bem, e que checagem
  automática (deles: decodificação restrita; aqui: `compat.py`) precisa ficar entre a LLM e o
  resultado final.
- Diferença benchmark deles vs dataset daqui: eles medem compilação/correção funcional geral de
  código de propósito geral; aqui é síntese de harness escalar restrito pra um model checker,
  domínio bem mais estreito, sem comparação direta de número.
- Limitação da comparação: não dá pra usar o número deles (redução de erro de compilação) como
  baseline de nada aqui — é motivação conceitual, não benchmark comparável. A técnica deles
  (decodificação restrita) exigiria acesso aos logits do modelo, que os backends usados aqui
  (API OpenAI, `codex exec`) não expõem — não é diretamente aplicável sem uma mudança de
  arquitetura maior (modelo local com acesso a logits).

---

### An Insight into Security Code Review with LLMs: Capabilities, Obstacles and Influential Factors (2024)

- Referência: Jiaxin Yu, Peng Liang, Yujia Fu, Amjed Tahir, Mojtaba Shahin, Chong Wang e Yangxiao Cai.
  Estudo empírico em revisão de código de segurança; preprint arXiv.
- Link: <https://arxiv.org/abs/2401.16310>
- Problema tratado: avaliar se LLMs conseguem detectar defeitos de segurança em código real e
  fornecer uma descrição mais detalhada do achado, em vez de responder apenas se o arquivo é
  vulnerável ou não.
- Técnica proposta: comparação de sete LLMs sob diferentes prompts, incluindo prompts com lista
  de categorias CWE, mensagem do commit e instruções de raciocínio. A resposta solicitada inclui
  localização, tipo do defeito, descrição e correção sugerida.
- Benchmark: 614 comentários de revisão identificando defeitos de segurança em quatro projetos
  open source, principalmente OpenStack e Qt, com 15 tipos predefinidos de defeito.
- Métricas: detecção do defeito, localização e tipo informados, consistência entre execuções e
  análise manual de problemas de qualidade nas respostas.
- Resultado principal: os autores observam que prompts com informação auxiliar, especialmente a
  lista de tipos CWE, alteram o desempenho; os modelos também produzem respostas vagas, detalhes
  incorretos e inconsistências entre execuções. O trabalho mostra que detectar o defeito e
  descrevê-lo corretamente são capacidades relacionadas, mas não equivalentes.
- Hipótese aplicável aqui: separar explicitamente duas medidas no pipeline: (1) localização da
  função/expressão suspeita e (2) classificação entre as oito categorias formais. A classificação
  pode receber uma lista fechada de categorias e few-shots específicos, sem obrigar a LLM a
  resolver localização e taxonomia na mesma saída. A consistência entre repetições também deve
  ser medida por etapa.
- Diferença benchmark deles vs dataset daqui: eles usam defeitos de segurança anotados em
  comentários de code review, código de arquivos completos e 15 tipos CWE; aqui são bugs reais de
  Python, avaliados no nível de função, com oito categorias e confirmação adicional pelo
  ESBMC-Python.
- Limitação da comparação: o estudo não prova que uma arquitetura em duas chamadas sempre supera
  uma chamada conjunta. Ele sustenta a separação das métricas e fornece evidência de que a saída
  detalhada pode falhar mesmo quando o modelo detecta um defeito.

---

### Bug In The Code Stack: Can LLMs Find Bugs in Large Python Code Stacks? (2024)

- Referência: Hokyung Lee, Sumanyu Sharma e Bing Hu. Benchmark BICS; preprint arXiv.
- Link: <https://arxiv.org/abs/2406.15325>
- Problema tratado: medir se LLMs conseguem encontrar um bug inserido em um grande contexto de
  código Python, evitando avaliar apenas snippets pequenos e isolados.
- Técnica proposta: construir pilhas de código a partir de blocos menores, inserir um bug sintático
  e pedir à LLM que informe tanto a linha quanto o tipo do bug.
- Benchmark: código Python com sete tipos de bugs sintáticos inseridos em diferentes tamanhos de
  contexto; o foco é a recuperação da informação relevante dentro do código.
- Métricas: identificação do bug, linha/localização e tipo do bug, além do efeito do tamanho do
  contexto e da diferença entre modelos.
- Resultado principal: o desempenho piora em ambientes de código quando o contexto cresce, e há
  diferenças substanciais entre modelos. O benchmark separa naturalmente o acerto de encontrar o
  local do bug do acerto de identificar o seu tipo.
- Hipótese aplicável aqui: registrar no resultado da etapa de detecção a expressão e a linha
  encontradas, mesmo quando a categoria estiver ausente ou marcada como `unknown`. Em seguida, a
  etapa de classificação pode receber esse trecho já localizado. Isso permite medir se o modelo
  encontrou o código correto antes de penalizá-lo por escolher a categoria errada.
- Diferença benchmark deles vs dataset daqui: BICS usa bugs sintáticos artificiais inseridos em
  grandes pilhas de Python; aqui usamos bugs reais de 42 repositórios, com categorias semânticas e
  avaliação formal por harness e ESBMC.
- Limitação da comparação: localizar um bug sintático em contexto grande é mais simples que
  distinguir `variable_misuse`, `none_misuse`, `invalid_precondition` e `integer_overflow` em
  código real. O trabalho justifica a decomposição das métricas, mas não fornece um baseline
  direto para as oito categorias deste projeto.
