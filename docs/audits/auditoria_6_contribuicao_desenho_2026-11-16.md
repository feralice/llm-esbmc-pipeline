# Auditoria 6: contribuição científica e desenho experimental (16/11/2026)

Documento de trabalho da Fernanda. Não é texto para orientador ou banca. Complementa `auditoria_pipeline_2026-11-16.md` (chamada aqui de "auditoria do pipeline"), `auditoria_0_inventario_2026-11-16.md` e `auditoria_1_bugsinpy_2026-11-16.md`. As auditorias 2 a 5 ainda não existiam em `docs/audits/` quando este texto foi escrito, então não foram usadas.

**Como foi feito.** Claude Code (Opus 5.5), só leitura, sem chamada de LLM, sem busca na web e sem rodar o pipeline. Li as três auditorias acima, os documentos de referência do repositório (`trabalhos_relacionados_2026-10-16.md`, `fichamento.md`, `leituras_recomendadas.md`, `literatura_auto_melhoria.md`, `notas_pyra_2026-11-09.md`, a lista de `artigos_estudo/`), o esqueleto `artigo.tex`, o registro dos scans e o script de detecção nas corrigidas. A telemetria de 16/11 foi somada com Python, sem gravar nada.

**Rótulos:** **[F]** fato conferido em arquivo ou artefato; **[I]** inferência minha; **[H]** hipótese a testar; **[NV]** não verificado. Toda referência bibliográfica aqui é **[NV]**: o repositório registra conferências feitas em 15 e 16/10, mas esta auditoria não as refez. Antes de entrar em qualquer texto, cada uma precisa ser conferida contra DBLP ou Crossref (agente `citation-verifier`).

**Sobre as propostas.** As perguntas de pesquisa, os desenhos e as regras abaixo são **opções** para você avaliar com o Lucas. Nenhuma delas é decisão sua, e algumas competem entre si.

---

## Sumário

1. Problema e objetivo
2. Contribuições: sustentadas e hipotéticas
3. Trabalhos relacionados que já estão no repositório
4. Perguntas de pesquisa propostas e desenho
5. Protocolo de avaliação independente
6. Experimentos essenciais e opcionais, com custo
7. Plano de publicação
8. Riscos metodológicos
9. Decisões que ficam com você

---

## 1. Problema e objetivo

### 1.1 Que problema o pipeline resolve

Formulação que os artefatos sustentam **[I, a partir de F]**: dada uma função Python real, já recortada, uma LLM levanta hipóteses de erro de execução (exceção não tratada). O pipeline tenta transformar cada hipótese numa evidência executável: um harness montado por código a partir de um JSON de tipos, verificado pelo ESBMC-Python e depois reexecutado no CPython. O objetivo prático é separar hipóteses da LLM que têm um cenário concreto de falha das que não têm.

Duas coisas o pipeline **não** faz hoje, e isso muda a formulação do problema:

- **Localizar a função.** A entrada já é a função rotulada; os 47 arquivos têm só as 53 funções do gabarito (auditoria do pipeline, achado 5) **[F]**. O problema medido é "dentro desta função, existe uma falha de execução, e qual?", e não "onde está o bug no projeto".
- **Provar o bug no programa real.** A confirmação vale para o harness, com `cut_after_suspect`, stubs e tipos escolhidos pela LLM (achado 8) **[F]**. Nos scans, os 5 CONFIRMED analisados à mão eram falsos no contexto real: chamador que captura a exceção ou entrada que a plataforma nunca envia (`achados_scans_para_artigo_2026-11-12.md`, "Lições") **[F nos documentos]**.

### 1.2 Unidade de análise

Há três unidades em uso, e misturá-las confunde os números **[F]**:

| Unidade | Quantidade em 16/11 | Onde aparece |
|---|---:|---|
| Bug (um PR integrado) | 47 | métrica oficial por bug |
| Função | 53 | uma chamada de detecção por função |
| Hipótese | 122 achados, 106 resultados, 105 únicas | vereditos do ESBMC e funil |

Proposta **[I]**: usar a **função** como unidade experimental (é nela que a LLM decide), o **bug** como unidade de relato para positivos, e tratar **projeto** como grupo nas análises, porque 5 projetos somam 24 dos 47 bugs (auditoria do pipeline, 5.1). Com negativos, a função também é a unidade natural: "função corrigida" e "função sem defeito conhecido" não têm bug para contar.

### 1.3 Hipóteses testáveis

Nenhuma destas foi testada de forma controlada até hoje **[F]**. Escrevo como H1 a H5 para as RQs da seção 4.

- **H1.** A LLM levanta hipóteses de exceção com mais frequência em funções com defeito do que nas mesmas funções corrigidas e em funções sem defeito conhecido.
- **H2.** Exigir veredito do ESBMC, além do replay, reduz alarmes em funções sem defeito mais do que reduz acertos em funções com defeito.
- **H3.** Uma parte relevante das confirmações não corresponde ao defeito do patch ou não é alcançável no programa real.
- **H4.** O conjunto de bugs confirmados é estável entre repetições da mesma configuração, dentro de uma faixa que dá para medir.
- **H5.** As recusas do ESBMC-Python em código real se concentram em poucas construções da linguagem.

### 1.4 Capacidades implementadas, demonstradas e alegadas

| Capacidade | Estado | Evidência |
|---|---|---|
| Detecção por função com prompt A1+A2 | implementada e usada | 53 chamadas em 16/11 **[F]** |
| Triagem pela própria LLM (`verifiable`) | implementada | 122 achados, 106 enviados **[F]** |
| Harness por código a partir de JSON de tipos | implementado e usado | 507 chamadas de síntese **[F]** |
| Grounding por AST (`verify/grounding.py`, "Locate a hypothesis in the real source") | implementado | docstring l. 1 **[F]**; efeito não isolado **[F]** |
| Self-healing guiado pelo erro do ESBMC | implementado | 66 hipóteses com healing em 16/11 **[F]** |
| Escalonamento de unwind, solver e tempo | implementado | auditoria do pipeline, Parte 3 item 6 **[F, subagente]** |
| Replay no CPython isolado | implementado | `verify/replay_worker.py` l. 285-330 **[F]** |
| Controle nas versões corrigidas | preparado, nunca rodado no pipeline atual | `scripts/preparar_deteccao_corrigidas.py` só monta a entrada e roda só a etapa `detection` (l. 57-60) **[F]** |
| Modo scan | implementado, inativo em 16/11 | auditoria do pipeline, Parte 3 **[F]** |
| Procedência do ESBMC e telemetria por chamada | implementadas | `commit.txt`, `llm_telemetry.json` (560 chamadas) **[F]** |

**Benefícios demonstrados [F]**, todos no conjunto de desenvolvimento e numa rodada:
- 13 de 47 bugs com cenário que levanta no harness a exceção do rótulo;
- 8 de 47 com a mesma exceção confirmada pelo ESBMC (17%, Wilson 95% de 9 a 30%);
- custo medido: US$ 42,04 em valor de API, US$ 5,26 por bug confirmado;
- limites concretos do ESBMC-Python relatados como issues.

**Alegações no repositório sem evidência suficiente [F na existência da frase; o problema é meu juízo, I]:**

| Onde | O que diz | Por que não se sustenta |
|---|---|---|
| `trabalhos_relacionados_2026-10-16.md:27` | "confirmação concreta no código original" | a confirmação é no harness (achado 8 da auditoria do pipeline) |
| `achados_scans_para_artigo_2026-11-12.md:36` | reencontrar o PR #189 "valida que o pipeline acha defeitos reais" | um caso já reportado, sem denominador; os outros CONFIRMED analisados eram falsos no contexto |
| `entendendo_o_pipeline.md:312` | "0 confirmações falsas nas versões corrigidas (2 rodadas)" | vale para motores antigos; `control-fixed-2026-10-06` teve 1 CONFIRMED na corrigida (ir_real_03, `docs/experimentos/README.md:145`); no pipeline de 16/11 o controle não rodou |
| `PLANO_2026-10-19.md:71` | "O teste fora da amostra da dissertação fica com a V2 (289 bugs)" | os 289 foram usados para ajustar o pipeline (auditoria 1, seção 7) |
| `leituras_recomendadas.md` §8.7 | contribuição 2 é a "ablação de hipótese" (`ablation.py`) | o próprio arquivo diz (l. 10) que `ablation.py` saiu do código |
| `artigo.tex:47` | "47 bugs reais de 20 projetos" | são 21 projetos (auditoria 0, seção 12) |
| tabela de experimentos, rodada de 06/11 | "fora da amostra, conforme registro" | não é limpa (auditoria do pipeline, achado 4) |

### 1.5 Contribuição de engenharia e contribuição científica

**[I]** Quase tudo que existe hoje é contribuição de engenharia: um sistema que funciona de ponta a ponta, com rastreabilidade boa. A parte científica depende de uma pergunta com comparação controlada, e as comparações feitas até agora são, na maioria, exploratórias (matriz de comparabilidade da auditoria do pipeline, Parte 4).

Também não dá para afirmar novidade. O próprio repositório já reconhece que o espaço "LLM tria, ferramenta confirma" está povoado (`leituras_recomendadas.md` §7.4) e que trabalhos do grupo do orientador fazem LLM + BMC para Python por tradução para C (`trabalhos_relacionados_2026-10-16.md`, itens 3 e 4). A diferença que sobra ("Python verificado direto, sem tradução, em bugs reais") é plausível, mas é afirmação de ausência, e só uma busca bibliográfica estruturada pode sustentá-la.

---

## 2. Contribuições: sustentadas e hipotéticas

### 2.1 Sustentadas pelos dados atuais (com o escopo certo)

1. **Um pipeline reprodutível na estrutura** (código, prompts, procedência do ESBMC, telemetria) que leva hipóteses de LLM a vereditos de BMC em Python sem tradução para C. **[F]** Engenharia.
2. **Um estudo de caso pré-registrado** em 47 bugs de CPS e IoT, declarado como conjunto de desenvolvimento: 13/47 e 8/47, com intervalos e com a variação de 2 a 3 bugs entre rodadas próximas. **[F]**
3. **Uma descrição do funil por bug**, mostrando onde as hipóteses param (18 a 20 bugs sem programa aceito pelo ESBMC). **[F]** Depende de fixar a regra de precedência.
4. **Relatos de limites do ESBMC-Python em código real**, com issues abertas (`possiveis_problemas/disciplina_pgene601/RECUSAS_ESBMC.md`, segundo a auditoria 0) **[F nos documentos]**. A auditoria do pipeline chama esta de "a contribuição mais sólida e independente da LLM".
5. **Uma lição metodológica documentada:** confirmação no harness não é bug no projeto, com os casos dos scans e do pymodbus_2921 como exemplos. **[F]**

### 2.2 Hipotéticas (dependem de experimento novo)

| Contribuição possível | Depende de | RQ |
|---|---|---|
| A verificação formal reduz falso alarme da LLM | negativos e braço "LLM + replay sem ESBMC" | RQ2 |
| A LLM discrimina funções com e sem defeito | negativos | RQ1 |
| Taxa de confirmações fiéis ao defeito e alcançáveis | auditoria manual com dois avaliadores | RQ3 |
| O resultado se repete e tem custo previsível | repetições da configuração congelada | RQ4 |
| O resultado vale fora do conjunto de desenvolvimento | conjunto independente (seção 5) | todas |
| Taxonomia de recusas do ESBMC-Python em código real | desdobrar LLM_ONLY e repetir num conjunto novo | opcional (H5) |

---

## 3. Trabalhos relacionados que já estão no repositório

Fontes: `trabalhos_relacionados_2026-10-16.md` (TR), `fichamento.md` (FI), `leituras_recomendadas.md` (LR), `literatura_auto_melhoria.md` (LA), `notas_pyra_2026-11-09.md` (PY), `artigos_estudo/` (AE, resumos em .md). Todas as entradas são **[NV]** nesta auditoria. Indico ano e local como o repositório registra.

**Inconsistências internas que já pedem nova conferência [F]:**
- **ESBMC-Python:** TR dá DOI 10.1145/3650212.3685304; FI diz "DOI da ACM não confirmado, citar pelo arXiv".
- **Tihanyi et al., "A New Era in Software Security":** TR dá 5 autores e DOI 10.1109/AST66626.2025.00020; FI lista 6 autores (com Youcheng Sun) e "DOI não encontrado".
- **Shivaji et al.:** TR diz "AISoLA 2025"; FI diz "3rd AI ISoLA 2026".
- **Dietterich (1998):** LR §5.5 marca como "citação de memória".

### 3.1 Classificação

| Eixo | Trabalhos no repositório | Fonte | Relação com esta pesquisa |
|---|---|---|---|
| **LLMs para detecção e revisão de bugs** | Ullah et al. (LLMs Cannot Reliably Identify...); Ding et al. (PrimeVul); Li et al. (Everything You Wanted to Know...); Tamberg e Bahsi; Dozono et al.; Kaniewski et al. (revisão sistemática); Zhou et al. (revisão e caminho à frente); Liu et al. (VulDetectBench); Ilić Vulićević (LLMs locais para bugs em Python); Kang et al. (localização explicável); Yang et al. (localização sem teste); "Bug In The Code Stack"; Jin e Chen (revisores com supercorreção); Gheyi et al. (bugs de refatoração com modelos pequenos); Hannan et al. e Camarato et al. (sensibilidade a exemplos e prompt) | FI, LR §1.4d, §7.5a, AE | quase todos medem vulnerabilidade em C/C++ ou Java; poucos são de Python. Servem para motivar falso positivo e sensibilidade a prompt |
| **Análise estática** | Dolcetti et al. (PYRA, linter para ciência de dados); Li et al. (IRIS); LLift; Wang et al. (LLMDFA); série "Hitchhiker's Guide" I, II e III; Du et al. (falso positivo em análise estática na indústria); preprints sobre viabilidade de caminho (arXiv 2506.10322) e filtragem de falso positivo (2601.22952); estudo de triagem de milhares de avisos (TKDD 2024) | PY, FI, LR §6.2, §7.4, §8 | o padrão é "ferramenta acha, LLM filtra"; aqui é o inverso ("LLM acha, ferramenta confirma"). mypy aparece só como ferramenta, sem artigo de referência |
| **Verificação formal e BMC** | Biere et al. (1999); Cordeiro, Fischer e Marques-Silva (ASE 2009); ESBMC v7.4; Farias et al. (ESBMC-Python, ISSTA 2024); Eilers e Müller (Nagini, CAV 2018); CEGAR (LR §6.3); Tihanyi et al. (visão geral de verificação formal a LLMs, 2025) | TR, FI, AE, LR | base teórica e a ferramenta usada |
| **Geração automática de harness** | Wang, Liu e Huang (HarnessLLM, Rust, ICSE 2026); Liu et al. (PromeFuzz); Lyu et al. (Prompt Fuzzing); Zhang et al. (How Effective Are They?, ISSTA 2024); Xu et al. (CKGFuzzer); OSS-Fuzz-Gen; FalseCrashReducer; Li et al. (Evident, Hitchhiker III); Sun et al. (Agentic Model Checking); Mukherjee e Delaware (SynVer) | TR, FI, LR §6.1, §7.3 | o mais próximo do passo de síntese. A maior parte é fuzzing em C/C++ ou Rust. FalseCrashReducer trata o mesmo problema de harness que cria falha irreal |
| **Grounding por AST** | Khati et al. (alucinação em código detectada por AST, arXiv 2601.19106); inferência de tipos: Peng et al. (TypeGen), Venkatesh et al. (tipos e grafo de chamadas), TypeEvalPy | LR §1.4c, FI | poucas referências; nenhuma sobre ancorar uma hipótese de bug numa expressão do código |
| **Validação de hipóteses e autocorreção** | Chen et al. (Self-Debug); Shinn et al. (Reflexion); Gou et al. (CRITIC); Huang et al. (LLMs Cannot Self-Correct Reasoning Yet); Adnan e Kuhn (decaimento do debug); Dantas et al. (limite 4/δ para sistemas LLM com verificador); Charalambous et al. (reparo com verificação formal); Tihanyi et al. (self-healing com ESBMC); self-consistency e universal self-consistency | FI, LA, LR §2 | sustentam o healing e o refinamento; Huang et al. sustenta exigir evidência externa |
| **Benchmarks de bugs Python e contaminação** | Widyasari et al. (BugsInPy, ESEC/FSE 2020); "Bug In The Code Stack"; Ramos et al. (memorização de benchmarks de bugs); De Koning et al. (teste metamórfico para memorização); Riddell et al. (contaminação em geração de código); Badertdinov et al. (SWE-rebench); Dwork et al. (reuso de holdout); CyberGym (não é Python) | LR §1.4, §8.6, FI, LA | base direta da seção 5 (exposição e contaminação) |
| **LLMs com ferramentas formais** | Shivaji et al. (LLM traduz Python e BMC); Orvalho e Kwiatkowska (PyVeritas); Wang et al. (execução simbólica de Python com geração por LLM); Li, Meng e Duck (AutoBug, OOPSLA 2025); Wu et al. (LLM e BMC para invariantes, ASE 2024); Pirzada et al. (invariantes para BMC, ASE 2024); Bhatia et al. (transpilação verificada); Chen et al. (Model-Bench); Yang et al. (especificações formais); Rego et al. (VeriFast); Shefer et al.; SpecGen; Wei et al. (vibe coding guiado por métodos formais); Erfan et al. (Dafny) | TR, FI, LR §1.2, §1.3, §3, §6.4 | os trabalhos mais próximos são Shivaji et al. e PyVeritas: traduzem para C e usam programas pequenos ou bugs plantados (segundo TR) |
| **Material sem formato de artigo** | slides "Cooperative AI-Assisted Formal Verification: Integrating LLMs with Model Checking for Scalable Software Assurance" (palestra do Lucas, `UFAM-2026-Cordeiro.pdf`, título lido nos metadados do PDF) | raiz | contexto do grupo; não é referência citável como artigo |

### 3.2 O que precisa de pesquisa bibliográfica depois

Nada abaixo está no repositório. Os nomes de ferramentas são pistas de busca, não referências.

1. **Ferramentas dinâmicas para Python** que seriam baselines naturais: geração automática de testes, execução simbólica e testes baseados em propriedade (por exemplo, procurar o que existe para Python além do Hypothesis, que o projeto já usa só como biblioteca) **[NV]**.
2. **Estudos empíricos de verificadores de tipo** (mypy, pyright) achando bugs reais. O artigo da disciplina cita mypy como baseline sem referência **[F]** (`artigo.tex:43`).
3. **Trabalhos que verificam Python direto com model checker e LLM**, sem tradução. É a busca que decide se a "diferença defensável" de TR se sustenta.
4. **Realismo de harness e alcançabilidade:** verificação de função isolada sem o contrato do chamador (o caso ir_real_03 e os scans mostram o problema). Termos de busca: execução simbólica sub-restrita, inferência de pré-condição a partir de chamadores.
5. **Avaliação de detectores com negativos pareados** (versão com bug contra versão corrigida) e com conjunto posterior ao corte do modelo.
6. **Bugs em software Python de CPS e IoT**: estudos empíricos do domínio, para justificar a amostra.
7. **Datasets de bugs Python mais novos que o BugsInPy**, para a seção 5.

---

## 4. Perguntas de pesquisa propostas e desenho

São quatro opções. Dá para ficar só com parte delas. RQ1 e RQ2 dependem dos mesmos negativos; RQ3 é quase toda manual; RQ4 é a mais cara em chamadas.

Notação dos braços (seção 6): **B0** LLM sozinha; **B1** LLM + harness + replay, sem ESBMC; **B2** pipeline completo; **T** ferramentas tradicionais.

### RQ1. A LLM distingue funções com defeito de funções sem defeito?

- **Motivação.** Hoje o nível "apontado" é 47/47 por construção (auditoria do pipeline, 5.2) **[F]**. Sem negativos, não há como saber se a LLM acha exceção em qualquer função.
- **Hipótese (H1).** A taxa de funções com hipótese do tipo de exceção esperado é maior nas funções com defeito do que nas corrigidas e nas sem defeito conhecido.
- **Variáveis.** Independente: condição da função (com defeito, corrigida, sem defeito conhecido do mesmo arquivo). Dependentes: função com alguma hipótese; função com hipótese do tipo esperado; número de hipóteses. Controladas: modelo, prompt, perfil, contexto do CLI, tamanho da função (registrar e estratificar).
- **Dataset.** Conjunto independente (seção 5), com os três tipos de função. Os 47 corrigidos servem como piloto dentro do desenvolvimento.
- **Baseline.** B0 é o próprio objeto. Comparação natural: mypy e pyright nas mesmas três condições.
- **Métricas.** Taxas por condição com Wilson; diferença pareada por bug (com defeito contra corrigida) com McNemar exato; AUC só se houver escore (hoje não há).
- **Procedimento.** Detecção congelada, uma chamada por função, três repetições, ordem das funções sorteada; avaliação automática pela regra pré-registrada.
- **Ameaças.** Versão corrigida muito parecida com a defeituosa (a LLM pode apontar a mesma expressão, agora guardada); funções sem defeito conhecido podem ter defeito real; contaminação.
- **Evidências existentes.** Variação de 22 a 26 na detecção pela linha em 48 casos da V2 (F27) **[F]**; nenhuma em negativos do pipeline atual.
- **Evidências necessárias.** Detecção nas corrigidas e em funções sem defeito, com repetições.

### RQ2. Quanto o ESBMC acrescenta em relação à LLM com replay?

- **Motivação.** É a pergunta que justifica usar verificação formal. Hoje só existe a diferença 13 contra 8 dentro de uma rodada, e o replay daquela rodada foi alimentado por reparos guiados pelo ESBMC **[F]**, então não é um braço "sem ESBMC" limpo **[I]**.
- **Hipótese (H2).** B2 tem taxa de confirmação em funções sem defeito menor que B1, com perda pequena em funções com defeito.
- **Variáveis.** Independente: braço (B0, B1, B2). Dependentes: confirmação no positivo (proxy de verdadeiro positivo) e no negativo (proxy de falso positivo), custo, tempo. Controladas: mesma detecção reaproveitada nos três braços, para isolar o efeito da verificação.
- **Dataset.** O mesmo da RQ1.
- **Baseline.** B1 é o principal. T (mypy, pyright, testes do PR) e B0 entram como contexto.
- **Métricas.** Por braço: confirmados em positivos e em negativos, com Wilson; precisão estimada no desenho balanceado; McNemar exato entre B1 e B2 por função; custo por confirmação.
- **Procedimento.** Rodar a síntese e o replay com o ESBMC desligado (B1) e ligado (B2) sobre as mesmas hipóteses. Confirmar no código se existe um modo sem ESBMC; **[NV]** não achei flag para isso nos módulos lidos.
- **Ameaças.** O healing só roda com erro do ESBMC, então B1 e B2 diferem em mais de um fator; o replay faz busca própria e pode achar cenários que o ESBMC não acha; mesma ressalva de harness da RQ3.
- **Evidências existentes.** 13 reproduzidos contra 8 confirmados em 16/11; o funil mostra 5 bugs com reprodução sem ESBMC **[F]**.
- **Evidências necessárias.** Braço B1 rodado de forma separada; negativos.

### RQ3. As confirmações correspondem ao defeito e são alcançáveis no programa real?

- **Motivação.** É a ameaça de construto mais grave: "reproduzido" mede o tipo da exceção em qualquer linha da função, no harness **[F]**; um CONFIRMED teve assinatura trocada pelo healing (pymodbus_2921) **[F]**; nos scans, 5 de 5 CONFIRMED analisados eram falsos no contexto **[F nos documentos]**.
- **Hipótese (H3).** Uma fração não desprezível das confirmações falha em pelo menos um de três critérios: (a) mesma expressão do patch; (b) harness sem mudança de semântica relevante; (c) entrada alcançável pelo chamador real.
- **Variáveis.** Para cada confirmação: os três critérios, cada um com sim, não ou não dá para decidir.
- **Dataset.** Todas as confirmações das rodadas da RQ2, positivas e negativas. Os 8 de 16/11 servem como piloto do protocolo de anotação.
- **Baseline.** Não se aplica; é um estudo descritivo com anotação humana.
- **Métricas.** Proporção que passa em cada critério e nos três; concordância entre dois anotadores (kappa de Cohen) numa parte comum.
- **Procedimento.** Guia de anotação escrito antes; dois anotadores (você e outra pessoa, a combinar com o Lucas) sem ver o braço de origem; desempate registrado. O critério (c) pode usar os três filtros dos scans (entrada real, chamador que captura, problema já reportado).
- **Ameaças.** Anotador único; critério (c) subjetivo; amostra pequena de confirmações.
- **Evidências existentes.** Caso pymodbus_2921; ir_real_03 (`docs/experimentos/README.md:233-237`); 13 rótulos que são a linha vizinha do guarda (auditoria do pipeline, 5.1) **[F]**.
- **Evidências necessárias.** O guia de anotação e o segundo anotador. Isso não depende de LLM.

### RQ4. O resultado se repete, e quanto custa?

- **Motivação.** Só há uma rodada da configuração congelada; entre rodadas parecidas, 2 a 3 bugs mudam **[F]**.
- **Hipótese (H4).** A concordância por função entre três repetições é alta o bastante para que uma diferença entre braços maior que a faixa observada seja interpretável. É uma hipótese descritiva: o valor de "alto o bastante" precisa ser fixado antes.
- **Variáveis.** Independente: repetição (detecção nova contra detecção reaproveitada). Dependentes: veredito por função e por bug; custo; tempo.
- **Dataset.** Os 47 (variação no desenvolvimento) e o conjunto independente.
- **Baseline.** Não se aplica.
- **Métricas.** Proporção de funções com o mesmo resultado nas três repetições; kappa de Fleiss; amplitude de 13/47 e 8/47; custo por bug confirmado, por repetição.
- **Procedimento.** Duas fontes de variação separadas: (i) detecção reaproveitada e só a verificação repetida (a "r2" já prevista no script, segundo a auditoria do pipeline); (ii) detecção nova em cada repetição.
- **Ameaças.** Modelo hospedado pode mudar entre repetições; contexto do CLI possivelmente variável (achado 10); limite de uso da assinatura interrompeu a rodada de 14/11 **[F]**.
- **Evidências existentes.** F27 (22, 23, 24) na V2; reavaliação de cinco rodadas com a regra atual **[F]**.
- **Evidências necessárias.** Três repetições congeladas; gravar a versão do CLI e o prompt completo enviado.

**Alternativa a uma das quatro (H5) [I].** Uma RQ sobre "que construções impedem o BMC de Python em código real" usa dados que já existem (recusas, LLM_ONLY desdobrado, issues) e quase não depende da LLM. Pode ser mais segura para a qualificação do que a RQ4, se o orçamento de chamadas for o gargalo.

---

## 5. Protocolo de avaliação independente

### 5.1 O que existe hoje e o que não é independente

| Fonte | Tamanho | Exposição ao pipeline | Pode ser teste independente? |
|---|---:|---|---|
| 47 da disciplina | 47 bugs, 21 projetos | conjunto de desenvolvimento, cerca de 10 decisões tomadas nele **[F]** | não |
| BugsInPy em `bugs_reais` | 259 | todos passaram por detecção completa; 12 ou mais decisões **[F]** | não |
| Coorte à mão de `bugs_reais` | 85 + 30 | selecionada por `VERIFICATION FAILED` em harness manual **[F]** | não, e ainda favorece o ESBMC |
| 219 recusados da coleta BugsInPy | 219 | recusados pelo critério de uma função; **[NV]** se algum passou pelo pipeline | não sem nova regra; BugsInPy é de 2020, risco alto de contaminação **[H]** |
| PRs triados em 08 e 12/10 (cerca de 2.300 títulos, 140 PRs abertos) | | vistos na seleção dos 47; o restante não rodou | não para os 140 abertos; os títulos só triados, com cautela |
| Repositórios dos scans | 10 CONFIRMED triados | sem gabarito; vistos | não; servem para estudo de falso positivo sem gabarito |
| Versões corrigidas dos 47 | 47 arquivos | nunca rodadas no pipeline atual **[F]** | não: são os mesmos bugs e o mesmo código do desenvolvimento. Servem de piloto do controle negativo |

**[F] Não existe hoje nenhum conjunto independente executado ou verificado.** Tudo abaixo é proposta.

### 5.2 Critérios para um conjunto novo

| Critério | Proposta | Por quê |
|---|---|---|
| Exposição anterior | excluir qualquer PR, commit ou função citado em `dataset/`, `artifacts/`, `docs/pgene601/cps_candidatos_*` e listas de triagem | ID mencionado é exposição (auditoria 1, seção 5.1) |
| Sobreposição com BugsInPy e com os 47 | excluir os mesmos projeto + arquivo + função; decidir antes se o mesmo projeto vale (ver abaixo) | os 47 têm 6 grupos com o mesmo arquivo; BugsInPy tem 16 grupos com a mesma função **[F]** |
| Projetos repetidos | duas opções: (a) só projetos novos, que mede generalização mas pode exigir outro domínio; (b) os mesmos 21 projetos com funções novas, mais fácil de minerar, mas que testa menos. Pode haver uma cota por projeto (por exemplo, no máximo 3 bugs) | 5 projetos somam metade dos 47 |
| Datas dos patches | só PRs integrados depois do corte de treino do modelo detector, com a data gravada no manifesto (`merged_at`) | os 47 não têm data **[F]**. O corte do `claude-sonnet-5-5` não está registrado no repositório **[NV]**: precisa vir da documentação do provedor. Com modelo hospedado e mutável, usar uma margem (por exemplo, a data de lançamento do modelo) |
| Conhecimento prévio do LLM | além da data, uma sonda opcional de memorização: mostrar a função com bug e pedir o PR, o título ou o patch; comparar com o real | Ramos et al. e De Koning et al. estão no repositório **[NV]** |
| Positivos | PR integrado que corrige exceção de execução nativa, confirmada pelo teste do PR ou pela leitura do patch, com `expected_type` | a métrica atual depende de `expected_type`; 64% dos BugsInPy são de valor errado **[F]** |
| Versões corrigidas | a mesma função no commit do merge, recortada pelo mesmo código | permite o par com defeito e corrigida |
| Funções sem defeito conhecido | 1 ou 2 funções do mesmo arquivo, no commit com bug, não tocadas pelo patch nem pelos 12 meses seguintes, sorteadas com semente | controla o arquivo e o estilo; "sem defeito conhecido" não é "sem defeito" |
| Viés a favor do ESBMC | sem bônus para construções que o ESBMC-Python suporta. Registrar o suporte como estrato **depois** da seleção e relatar as taxas no total e no subconjunto suportado | os critérios dos 47 davam bônus ao que o ESBMC cobre **[F]** |
| Quem rotula | você, sem ver resultados do pipeline; segundo rotulador em pelo menos 20% | rótulo único nos 47 **[F]** |
| Tamanho | ver 5.4 | |

### 5.3 Passo a passo

1. **Escrever a regra de seleção e o plano de análise** num arquivo novo (sugestão: `docs/protocolo/conjunto_independente.md`), com o modelo da seção 5.5. Commitar com data **antes** da primeira consulta à fonte.
2. **Congelar o pipeline**: tag, commit, binário do ESBMC (sha256), versão do Claude CLI, prompt completo enviado por chamada. Antes disso, resolver o achado 10 da auditoria do pipeline (contexto injetado pelo CLI), senão a entrada do modelo não se reproduz.
3. **Fazer as consultas** exatamente como escritas, gravando a saída bruta com data e hora.
4. **Aplicar a exclusão por exposição** com um script de leitura que cruza os candidatos com `dataset/`, `artifacts/` e as listas de candidatos. Guardar a lista do que saiu e por quê.
5. **Aplicar os critérios de inclusão** na ordem escrita, registrando o motivo de cada recusa. Parar no número-alvo pela ordem sorteada, não por escolha.
6. **Rotular** positivos (`expected_type`, expressão, linha) antes de qualquer execução. O segundo rotulador faz a sua parte de forma independente. Calcular kappa.
7. **Montar as entradas** (com defeito, corrigida, sem defeito conhecido) com o mesmo código de recorte, gravando hashes. Embaralhar a ordem e esconder a condição no nome do arquivo.
8. **Rodar** os braços do plano, com o número de repetições escrito no passo 1.
9. **Avaliar** com o código de avaliação no commit fixado no passo 1. Rodar a análise principal exatamente como escrita; o resto entra como exploratório.
10. **Relatar tudo**, incluindo inconclusivos e falhas de infraestrutura. Uma mudança no pipeline depois do passo 8 invalida o conjunto como teste: ele vira desenvolvimento, e um conjunto novo seria necessário.

### 5.4 Tamanho

Contas com a aproximação normal, só para ordem de grandeza **[I]**:
- estimar uma taxa perto de 17% com meia largura de 10 pontos pede cerca de 54 positivos; com 7 pontos, cerca de 110;
- zero alarmes em 47 negativos ainda deixa o limite superior de Wilson em 7,6%; em 60, 6,0%;
- o poder do McNemar entre B1 e B2 depende do número de pares discordantes, que hoje não dá para prever. Um piloto (os 47 corrigidos) ajudaria a estimar.

Uma meta possível: 60 positivos, com as 60 corrigidas e 60 a 120 funções sem defeito conhecido. A mineração dos 47 ocupou cerca de uma semana de calendário (listas de candidatos de 08 e 12/10, entrada no dataset em 15/10) **[F nas datas dos arquivos]**. Só a segunda rodada triou cerca de 2.300 títulos para chegar aos extras **[F]**, então o rendimento por título é baixo **[I]**.

### 5.5 Modelo de regra pré-registrada (campos a preencher)

```
Data e commit deste documento:
Pergunta(s) de pesquisa cobertas:
Fonte e consultas exatas (copiar a linha de comando):
Janela de datas de merge:            (e justificativa do corte do modelo)
Projetos permitidos:                  (novos, mesmos 21, cota por projeto)
Inclusão, em ordem:
Exclusão por exposição:               (arquivos e pastas cruzados)
Número-alvo e regra de parada:
Semente do sorteio:
Rotulagem:                            (quem, guia, parte com segundo rotulador)
Pipeline congelado:                   (tag, commit, ESBMC sha256, CLI, modelo)
Braços e repetições:
Métrica principal (uma só):
Métricas secundárias:
Tratamento de inconclusivos:          (seção 6.4)
Análise estatística:                  (intervalo, teste, correção para múltiplas comparações)
O que invalida o conjunto:
```

---

## 6. Experimentos essenciais e opcionais, com custo

### 6.1 Base para estimar custo (telemetria real de 16/11) [F]

| Item | Valor |
|---|---:|
| Detecção | 53 chamadas, US$ 4,44, cerca de US$ 0,084 por função |
| Síntese | 507 chamadas para 106 hipóteses, US$ 37,61, cerca de US$ 0,355 por hipótese |
| Hipóteses enviadas ao ESBMC por função | cerca de 2,0 (106/53) |
| Rodada completa por função | cerca de US$ 0,79 (42,04/53) |
| Tempo de parede da rodada | cerca de 4 h 40 min (13:11 a 17:51), cerca de 5,3 min por função |
| Tempo somado das chamadas de LLM | 0,26 h na detecção e 1,28 h na síntese |

Os valores são o custo que o CLI informa em valor de API. A rodada foi paga pela assinatura (`billing: assinatura`) **[F]**. O crédito de API que você tem é de US$ 100 (memória do projeto) **[NV aqui]**. A rodada de 14/11 parou no limite de uso da assinatura com 28,4 M tokens **[F]**, então o risco prático é a cota, não só o dinheiro.

### 6.2 Braços e ferramentas

| Braço | O que roda | Custo de LLM | Observação |
|---|---|---|---|
| B0, LLM sozinha | só a detecção | US$ 0,084 por função | já existe para os 47 (16/11): custo zero para reanalisar |
| B1, LLM + harness + replay, sem ESBMC | detecção, síntese, replay | detecção + síntese, menos os reparos do ESBMC | precisa de um modo sem ESBMC **[NV]** |
| B2, pipeline completo | tudo | cerca de US$ 0,79 por função | |
| T1, mypy padrão e `--check-untyped-defs` | sem LLM | zero | já rodado nos 47 (2/47 e 5/47) **[F]** |
| T2, pyright | sem LLM | zero | existe um `pyrightconfig.json` não versionado na raiz; **[NV]** se já foi usado como baseline |
| T3, testes do PR | sem LLM | zero | 10/47 e 36 sem teste **[F]**; no conjunto novo só cobre parte |
| T4, ESBMC sem LLM | motor com specs gravadas ou genéricas | zero | já houve rodadas assim em outubro (F6, F11) **[F]**; mede quanto a LLM acrescenta |
| T5, ferramentas dinâmicas de Python | sem LLM | zero | depende da busca 3.2, item 1 |

Para a comparação ser justa, todos os braços recebem a mesma unidade (a função recortada) e são contados na mesma unidade (função ou bug, com a regra escrita antes) **[I]**. Hoje mypy, testes e pipeline usam unidades diferentes (achado 9) **[F]**.

### 6.3 Repetições e controles negativos

- **Repetições:** três da configuração congelada por braço com LLM. Separar a variação da verificação (detecção reaproveitada) da variação da detecção (detecção nova).
- **Controle pareado:** as versões corrigidas. Uma CONFIRMED do mesmo `expected_type` na função corrigida conta como alarme falso ou como correção incompleta, e vai para triagem manual.
- **Controle não pareado:** funções sem defeito conhecido. Toda CONFIRMED vai para triagem com os critérios da RQ3, porque pode ser defeito real.
- **Controle barato sem LLM:** reexecutar as specs gravadas de 16/11 contra as versões corrigidas, como `control-fixed-2026-10-06` fez com `scripts/v2_replay_specs.py` **[F]**. Mede se o harness continua falhando quando o código foi corrigido. **[NV]** se o script ainda é compatível com os artefatos de 16/11 (última mudança em 02/11).

### 6.4 Inconclusivos

Proposta **[I]**:
- Escrever antes as categorias: recusa por limite de linguagem; erro interno do ESBMC (`esbmc_crash`); erro de contexto do harness; limite de voltas, unwind ou tempo; falha de infraestrutura ou de chamada; "outro".
- Na análise principal, inconclusivo conta como "não confirmado", que é a leitura conservadora para positivos.
- Nos negativos, inconclusivo conta como "sem alarme", o que favorece o pipeline. Por isso a taxa de inconclusivos precisa sair ao lado da taxa de alarme, por condição.
- Como sensibilidade, recalcular excluindo os inconclusivos.
- Relatar `esbmc_crash` à parte, como falha da ferramenta e não da LLM (auditoria do pipeline, 7.2).

### 6.5 Experimento mínimo viável: o que cabe antes de 30/11

Resposta honesta **[I]**: **a avaliação independente não cabe antes de 30/11.** Faltam a regra pré-registrada, a mineração, a rotulagem com segundo rotulador e as rodadas. Fazer isso em uma semana repetiria os problemas que as auditorias acharam (regra escrita olhando candidatos, rótulo único, rodada única). O artigo da disciplina cabe como **estudo exploratório no conjunto de desenvolvimento**, com controles que dá para rodar a tempo:

| # | Experimento | LLM? | Custo estimado | Tempo | Responde a |
|---|---|---|---:|---|---|
| E0 | sensibilidade da métrica de 16/11 (só expressão; sem os casos de healing com troca de tipo; ESBMC com a exceção como violação principal) | não | zero | horas | RQ3 piloto |
| E1 | B0 nos 47: reanálise das hipóteses de 16/11 por tipo de exceção | não | zero | horas | RQ1 (só positivos) |
| E2 | controle barato: specs de 16/11 contra as corrigidas | não | zero | horas, se o script funcionar | RQ2 piloto |
| E3 | datas dos 47 PRs pela API do GitHub | não | zero | 1 h | contaminação |
| E4 | desdobrar LLM_ONLY e fixar a precedência do funil | não | zero | horas | H5 |
| E5 | teste do contexto injetado pelo CLI | 1 chamada | centavos | minutos | reprodutibilidade |
| E6 | detecção nas 47 corrigidas (`scripts/deteccao_corrigidas.sh --execute`) | sim | cerca de US$ 4,4 | cerca de 20 min de LLM | RQ1 piloto |
| E7 | verificação das hipóteses de E6 | sim | até cerca de US$ 38, se a taxa de hipóteses for a mesma | cerca de 4 h | RQ2 piloto |
| E8 | r2 nos 47 (detecção reaproveitada, verificação repetida) | sim | cerca de US$ 38 | cerca de 4 h | RQ4 piloto |

Soma dos pagos (E5 a E8): cerca de US$ 80 em valor de API, se tudo rodar uma vez, dentro do crédito de US$ 100 mas sem folga para repetir. **[NV]** se E7 roda com o código atual: o script de preparação só chama a etapa `detection`. E6 e E7 continuam no desenvolvimento, então medem alarme **no conjunto onde o pipeline foi ajustado**, e o texto precisa dizer isso.

Uma priorização possível: E0 a E5 primeiro (sem custo); depois E6; E7 e E8 só se sobrar cota e tempo para escrever. Qualquer rodada paga precisa da sua autorização antes.

### 6.6 Avaliação ideal para publicação

- Conjunto independente da seção 5: cerca de 60 positivos, 60 corrigidas e 60 a 120 funções sem defeito conhecido (180 a 240 funções).
- Braços B0, B1, B2, T1 a T4 (e T5 se a busca achar ferramenta adequada).
- Três repetições dos braços com LLM.
- Anotação da RQ3 com dois anotadores.
- Opcional: um segundo modelo detector. Já existe uma rodada com Codex nos 47 (03/11, 39 com hipótese certa, `tabela_experimentos.md`) **[F]**, mas ela não é comparável com a de 16/11.

Custo estimado **[I]**, supondo a mesma taxa de hipóteses por função (os negativos podem gerar menos):
- uma repetição de B2 em 200 funções: cerca de US$ 160 e 18 h de parede;
- três repetições: cerca de US$ 480;
- B1 reaproveitando a detecção: menos que B2, por não ter os reparos do ESBMC; **[NV]** quanto.

Isso passa do crédito de API. As opções são espalhar as rodadas pela assinatura em vários dias, reduzir o conjunto ou repetir só a verificação. A decisão é sua e do Lucas.

---

## 7. Plano de publicação (proposta)

| Marco | Data | O que dá para afirmar | O que entra |
|---|---|---|---|
| Artigo da disciplina (PGENE601) | até 30/11/2026 | só a lista "sustentadas" da auditoria do pipeline (Parte 14), declarando conjunto de desenvolvimento | 47 bugs, rodada de 16/11, E0 a E5, e E6 a E8 se couberem; baselines como contexto; seção de ameaças forte |
| Qualificação | até fevereiro de 2027 | RQs, protocolo e, se der, resultado preliminar no conjunto novo | RQs escolhidas, regra pré-registrada commitada, conjunto minerado e rotulado, resultados do desenvolvimento como estudo exploratório |
| Artigo de pesquisa | depois da qualificação | as RQs respondidas no conjunto independente | avaliação ideal (6.6) e busca bibliográfica da seção 3.2 |

**Cronograma sugerido até a qualificação [I], deixando folga:**
- até 30/11: artigo da disciplina;
- primeira quinzena de dezembro: escolher as RQs com o Lucas, fazer a busca bibliográfica, escrever a regra e commitar;
- segunda quinzena de dezembro: mineração e rotulagem (o segundo rotulador pode atrasar nas festas);
- até meados de janeiro: rodadas no conjunto novo;
- segunda quinzena de janeiro: análise e texto;
- fevereiro: folga e revisão.

Para não pôr a qualificação em risco, o texto da qualificação não deveria depender dos resultados do conjunto novo. Se as rodadas atrasarem, ele entra como protocolo pré-registrado com piloto **[I]**.

---

## 8. Riscos metodológicos

| Risco | Efeito | Mitigação proposta |
|---|---|---|
| Conjunto de desenvolvimento usado como teste | número otimista | conjunto novo com regra pré-registrada; no texto, chamar os 47 de desenvolvimento |
| Sem negativos | não dá para falar de precisão nem de falso positivo | corrigidas e funções sem defeito conhecido |
| "Reproduzido" frouxo (tipo da exceção, qualquer linha, no harness) | construto inflado | métrica principal mais estrita, escrita antes; a atual como secundária |
| Confirmação no harness, não no projeto | afirmação de bug real indevida | RQ3; linguagem cuidadosa no texto |
| Healing muda semântica (pymodbus_2921) | confirmação sobre outro programa | registrar mudanças de assinatura e relatar com e sem esses casos |
| Rodada única e LLM sem semente | diferenças de 2 a 3 bugs sem significado | três repetições; separar variação da detecção e da verificação |
| Contexto do CLI possivelmente variável (achado 10) | entrada não reproduzível | testar com uma chamada (E5); se confirmado, bloquear ou trocar para a API com parâmetros gravados |
| Contaminação do modelo | detecção por memória | janela de datas, sonda de memorização |
| Seleção favorável ao ESBMC | generalização indevida | sem bônus na seleção; estrato de suporte relatado à parte |
| Agrupamento por projeto e por arquivo | intervalos estreitos demais | cota por projeto; bootstrap por projeto ou modelo misto |
| Rotulador único | gabarito com erro | segundo rotulador e kappa |
| Baselines em unidades diferentes | comparação injusta | mesma unidade e mesma entrada para todos os braços |
| Reuso adaptativo do conjunto novo | o conjunto novo vira desenvolvimento | uma consulta por braço planejado; mudança no pipeline invalida o conjunto (Dwork et al. está no repositório, **[NV]**) |
| Cota da assinatura e crédito de API | rodada interrompida, como em 14/11 | rodadas menores, com checkpoint, em dias diferentes |
| Afirmação de novidade sem revisão | rejeição | busca da seção 3.2 antes de escrever "primeiro" ou "novo" |

---

## 9. Decisões que ficam com você

1. Quais RQs adotar (todas, só RQ1 e RQ2, ou trocar RQ4 pela de recusas do ESBMC).
2. Se o conjunto novo usa só projetos novos ou os mesmos 21 com funções novas.
3. Qual é a métrica principal pré-registrada (uma só).
4. Quais de E6, E7 e E8 rodar antes de 30/11, com o custo da tabela 6.5.
5. Quem será o segundo rotulador e o segundo anotador.
6. Se a detecção continua pelo Claude CLI ou passa para a API com parâmetros gravados.

---

## Declaração de uso de IA

Este documento foi escrito por Claude Code (Opus 5.5) a pedido da Fernanda, a partir de leitura do repositório. As RQs, o desenho, os critérios e as estimativas são propostas da IA, não decisões da pesquisadora. Nenhuma referência foi conferida nesta sessão. Não houve revisão humana até o momento desta redação.
