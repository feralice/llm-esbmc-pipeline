# Auditoria científica do pipeline LLM + ESBMC (16/11/2026)

Documento de trabalho para a Fernanda ler e, depois, planejarmos juntas os próximos passos. Não é texto para orientador ou banca.

## Como esta auditoria foi feita

- **Quem fez:** Claude Code (modelo Opus 5.5), numa sessão com três subagentes de leitura (arquitetura do código, histórico experimental, dataset). Eu conferi por conta própria as afirmações dos subagentes que pesam no resultado. Duas estavam erradas e foram corrigidas (ver "Erros dos subagentes", no fim).
- **Só leitura.** Nenhum experimento, chamada de LLM, instalação ou alteração no repositório. Os cálculos foram feitos em memória a partir dos JSON existentes. Num caso importei `evaluate_functions` do próprio código para reaplicar a regra atual a rodadas antigas, sem gravar nada (`PYTHONDONTWRITEBYTECODE=1`).
- **Lido no código:** avaliador por função, veredito final, replay, laço de verificação, self-healing, backend `claude_cli`, perfil `congelado` e script de execução. Outros módulos foram lidos só em parte (subagente). **Sem leitura completa:** `grounding.py`, `spec.py`, `caller_facts.py`, `slicing.py`, `value_oracle.py`.
- **Lido em documentos:** `docs/experimentos/README.md` (inteiro, pelo subagente), planos, execuções do Codex, regra de acerto, congelamento, origem dos 47.
- **Dados brutos recalculados:** `artifacts/pgene601/congelado-2026-11-16-r1/v2_verify_report.json` e `llm_telemetry.json`. Também foram reavaliados `v2_verify_report.json` de 06/11, 07/11, 09/11 e 11/11.
- **Rótulos usados no texto:** **[F]** fato verificado no código ou nos artefatos; **[I]** inferência; **[H]** hipótese a testar; **[NV]** não verificado.

---

## Parte 1. Resumo executivo (dez achados)

1. **[F] Os números de 16/11 conferem.** Recalculei a partir do JSON bruto e cheguei a 13 de 47 "apontados e reproduzidos" e 8 de 47 "confirmados pelo ESBMC". Os denominadores estão certos: 47 bugs, 106 resultados de hipótese, 105 hipóteses únicas. Custo de US$ 42,04 e 11,45 M tokens, também conferidos. O pré-registro das regras (commit `f086e22` às 13:11:11, rodada iniciada às 13:11:17) é real. É o ponto mais forte do trabalho até agora.

2. **[F] A incerteza é grande.** 8/47 = 17,0%, com Wilson 95% de 8,9% a 30,1%. Reamostrando por projeto, o intervalo vai de 6,1% a 33,3%. 13/47 = 27,7% (Wilson 16,9% a 41,8%). Com uma rodada só, não dá para separar efeito de variação.

3. **[F] O conjunto de bugs confirmados muda entre rodadas próximas.** Reapliquei a regra atual às rodadas antigas. Entre 11/11 e 16/11, 7 bugs aparecem nas duas, 2 só em 11/11 e 1 só em 16/11. Só 4 bugs (blinka_434, gpiozero_716, paho_118, simpleio_43) aparecem nas cinco rodadas. Diferenças de 1 a 3 bugs entre rodadas não podem ser atribuídas a mudanças no pipeline.

4. **[F] Os 47 são conjunto de desenvolvimento, e a contaminação é maior do que dizem os documentos.** Pelo menos 10 mudanças no pipeline foram motivadas ou medidas nesses 47. Entre elas estão a edição do prompt A2 (08/11, ainda vigente em 16/11) e a regra de parada do reparo, calibrada nas rodadas de 09, 11 e 14/11. A rodada de 06/11, chamada de "fora da amostra", também não é limpa: vieram antes as sondas de 18/10 e as melhorias de 03 a 05/11, medidas nos casos GPS e MAVProxy dos 47.

5. **[F] O nível "apontado" não mede localização, e não há negativos.** Cada arquivo de entrada só tem as funções rotuladas (53 funções, todas no rótulo). Nenhuma função sem bug foi analisada. A detecção nas versões corrigidas foi preparada, mas não rodou. Por isso precisão, falso positivo e especificidade **não podem ser calculados**.

6. **[F] "Reproduzido no CPython" é um critério mais frouxo do que o nome sugere.** Basta que o replay, rodando o *harness*, levante uma exceção do mesmo *tipo* do rótulo em qualquer linha da função. A linha não precisa ser a do bug. O replay faz uma busca própria em domínios pequenos e não reexecuta o contraexemplo do ESBMC. Dos 13 reproduzidos, 2 (pycomm3_331 e piouart_6) só entram por uma regra do avaliador que aceita falha fora da expressão suspeita.

7. **[F] Numa das 8 confirmações, o ESBMC verificou um programa com o tipo do parâmetro trocado.** No pymodbus_2921, o self-healing trocou `data: bytes` por `bytearray`, voltou para `bytes` e terminou em `data: str`. Só depois disso saiu CONFIRMED. O replay usou `data: bytes`. A exceção é a mesma (IndexError em `data[6]`), mas a prova formal é sobre outra assinatura.

8. **[F] As confirmações valem para o harness, não para o programa real.** Os harnesses cortam o código depois da suspeita (`cut_after_suspect`), trocam imports por stubs não determinísticos e geram atributos com tipos escolhidos pela LLM (por exemplo, `_pwmpin: Optional[object]` no blinka_434). O relatório do próprio pipeline avisa que isso "não prova alcance pelo código real". O artigo precisa dizer o mesmo.

9. **[F] A comparação com baselines ainda não está pronta.** mypy acha 2/47 (5/47 com `--check-untyped-defs`) e os testes do PR, 10/47. Os três usam unidades de contagem diferentes da métrica do pipeline, e 36 bugs não têm teste no PR. Falta um baseline "só LLM" e falta um baseline que receba a mesma informação de localização que o pipeline recebe.

10. **[H] O contexto enviado ao modelo pode incluir material da sua conta.** Cada chamada de detecção tem cerca de 36 mil tokens de entrada para uma função curta. O modo isolado troca o prompt de sistema e roda numa pasta vazia, mas o help da própria flag avisa que o CLAUDE.md global e os hooks "podem ser" lidos (`cli_args.py:255-259`). Seu CLAUDE.md global descreve a pesquisa (LLM + ESBMC para bugs de runtime), e há hooks de sessão ativos. Se isso entra na detecção, a entrada do modelo depende da máquina e não se reproduz em outro lugar. É hipótese até ser testada.

**Pontos positivos [F]:**
- O pré-registro de 16/11 foi de verdade.
- A procedência do ESBMC é gravada (commit, sha256, data do binário).
- A telemetria cobre todas as 560 chamadas.
- A regra por função deixou a métrica mais conservadora: pela regra antiga, 14 a 15 bugs contavam como confirmados.
- O relatório já avisa sobre as próprias limitações.
- Não achei vazamento do gabarito para os prompts, dentro do que foi lido.

---

## Parte 2. Mapa de evidências

| # | Achado | Fonte | Local | Evidência | Confiança |
|---|---|---|---|---|---|
| 1 | 13/47 e 8/47 conferem | `congelado-2026-11-16-r1/v2_verify_report.json` | `evaluation.by_function` | recálculo caso a caso | F, alta |
| 2 | 106 resultados para 105 hipóteses | idem, `results` | id `efd0d98e1388` (pyspartn_4) duas vezes | `Counter` dos ids | F |
| 3 | Pré-registro anterior à rodada | `git log f086e22`; `commit.txt` | 13:11:11 contra 13:11:17 | horário do commit e do arquivo | F |
| 4 | "Reproduzido" = tipo da exceção em qualquer linha da função | `src/research_pipeline/v2_evaluator.py` | `_replayed_exception`, l. 279-289 | aceita `other_failure` dentro de `target_range` | F |
| 5 | Replay faz busca e não reexecuta o contraexemplo | `verify/replay_worker.py` | `main`, l. 285-330 | sementes do contraexemplo e depois domínio pequeno | F |
| 6 | CONFIRMED exige só o tipo da exceção no ESBMC | `verify/outcome.py` | `final_verdict`, l. 126-143 | `replay.exception_type in reading.exceptions` | F |
| 7 | Healing trocou o tipo no pymodbus_2921 | `results[].healing` do pymodbus_2921; `programs/8432febfbe95_a0.py:22` | rodadas 0 a 3 | `data: str` no programa do ESBMC, `data: bytes` no replay | F |
| 8 | Laço de refinamento pede à LLM uma assunção que exclua outra falha | `verify/loop.py` | l. 327-373, `MAX_REFINEMENTS=2` | texto de `_refinement_feedback` | F |
| 9 | Controle nas corrigidas inativo | `verify/loop.py` | l. 434-439 (segundo o subagente) | `fixed_sources` só para VALUE_ORACLE (A15 inativo) | F (subagente) |
| 10 | Arquivos de entrada só têm as funções rotuladas | `dataset/disciplina_pgene601/funcao_com_bug` | AST | 47 arquivos, 53 funções, todas no rótulo | F |
| 11 | A2 editado após testes nos 47 e vigente em 16/11 | `git show 2b148ba` | `A2_checklist.txt` | `merge-base --is-ancestor 2b148ba f086e22` | F |
| 12 | Regra de parada do reparo calibrada nos 47 | mensagem de `f55cc5a` | | "cortaria 55 a 60%..." | F (subagente) |
| 13 | Conjunto confirmado instável | reavaliação em memória | 5 relatórios | tabela da Parte 6 | F, com ressalva de esquema |
| 14 | Funil por bug depende da ordem de precedência | `scripts/relatorio_bugs.py` (não commitado) | `STAGES`, `stage_of` | "recusado" vem antes de "inconclusivo" | F |
| 15 | Sem temperatura nem semente | `llm/backends/claude_cli.py` | l. 27-42 | não há flag de amostragem | F |
| 16 | CLAUDE.md global e hooks podem entrar | `cli_args.py` | l. 255-259 | texto do help | H |
| 17 | Ressalva do pymodbus_2980 cita a função errada | `manifest.json` e patch | hunk `@@ -169` em `WriteFileRecordRequest.decode` (l. 170) | o manifesto diz `ReadFileRecordResponse.decode` (l. 121) | F |
| 18 | Datas dos PRs ausentes no dataset | `manifest.json` | `provenance` | não há `merged_at` | F |
| 19 | Documentação do pipeline desatualizada | `docs/projeto/entendendo_o_pipeline.md` | l. 1 ("estado de 30/09") | faltam healing, LLM_ONLY, refinamento | F |
| 20 | ESBMC rodou sem `--no-pointer-check --no-align-check` | `config.esbmc_command` | binário cru | o wrapper que adiciona as flags não foi usado | F (subagente) |

---

## Parte 3. Arquitetura real (perfil `congelado`)

Fluxo de uma rodada (`scripts/rodar_47_ruido.sh` chama `src/main.py`, `mode_v2`):

1. **Entrada.** São 47 arquivos de `funcao_com_bug`, recortados à mão, com 1 ou 2 funções cada (53 unidades). **[F]** A localização no nível de função já vem dada pelo dataset.

2. **Detecção.** Uma chamada por função, com `claude-sonnet-5-5` via `claude -p`. O prompt é `system_prompt_v2.txt` mais as variantes A1 e A2. A função chega renomeada para `target_function`, sem docstring e sem comentários. Os metadados são linhas, parâmetros e type hints. **[F]** Não entram o arquivo, os chamadores nem o caminho. "A5" é só o nome que os documentos dão a A1+A2; não existe no código. Não achei passagem de `expected_type`, patch ou manifesto para o prompt **[F nos módulos lidos; NV em `grounding.py`, `spec.py` e `caller_facts.py`]**.

3. **Triagem.** A própria LLM marca cada achado como `verifiable` ou não: 122 achados, 106 enviados ao ESBMC, 16 retidos. **[F]**

4. **Especificação do harness.** A LLM devolve só JSON (`params`, `attributes`, `stubs`, `assumptions`), com até 2 reparos alimentados pelo erro. As assunções viram `__ESBMC_assume`. A validação delas é só sintática. **[F]**

5. **Transformações.** Feitas pelo código, não pela LLM: `cut_after_suspect`, `none_guards`, `stubbed_imports`, `unused_definitions_removed`, `nondet_clock` e regras de compatibilidade ligadas por sondas. **[F]** O replay roda o programa *anterior* a essas reescritas.

6. **ESBMC.** `--unwind 5 --multi-property`, com escalonamento:
   - unwind 10 e 20, depois `--incremental-bmc` e `--k-induction`;
   - em timeout, troca de solver e reexecução com 300 s;
   - aceita contraexemplo parcial obtido em timeout se o replay reproduzir (1 CONFIRMED na rodada).

   **[F, subagente]** A documentação diz "--unwind 5 fixo".

7. **Self-healing (`error+kb`).** Roda quando o ESBMC recusa o programa (UNSUPPORTED, MISSING_DEPENDENCY, GROUNDING_FAILED). Até 3 rodadas por obstáculo e 9 no total; para quando a mensagem não muda (regra nova de 16/11). Pode:
   - editar o código fora do corpo (vale também para o replay);
   - simplificar o corpo, desde que a expressão suspeita fique (só no ESBMC);
   - escrever stubs;
   - mover a hipótese para outra função.

   **[F]** Na rodada, 66 hipóteses passaram por healing. A regra "só o que o ESBMC precisa" existe apenas no texto do prompt, sem verificação no código.

8. **Refinamento.** Se o replay falha antes da expressão suspeita, a LLM recebe o pedido de "adicionar uma assunção que exclua a entrada que faz essa linha falhar" (até 2 vezes). **[F]** Nenhum código verifica se a assunção é plausível no programa real. Na rodada, só uma confirmação usou esse caminho (pymodbus_2980, com `len(data) == 0`), e ela não está entre as 8. As 8 confirmações por bug tiveram uma única tentativa de especificação, sem assunções.

9. **Replay no CPython.** Busca determinística, com até 400 execuções isoladas (sem rede, `-I -S`):
   - uma passada curta com os valores do contraexemplo;
   - depois a enumeração de domínios pequenos (int de -1 a 2, `""`/`"a"`, listas de até 2 elementos).

   **[F]**

10. **Veredito.** **[F]**
    - CONFIRMED: ESBMC acha violação, o replay reproduz na expressão suspeita e o tipo da exceção do replay está entre os que o ESBMC listou.
    - UNVALIDATED: violação sem replay compatível.
    - OTHER_FAILURE: o replay falha em outra linha.
    - LLM_ONLY: o ESBMC nunca aceitou o programa.

11. **Avaliação por função.** **[F]**
    - Apontado: há hipótese numa função do rótulo.
    - Apontado e reproduzido: o tipo da exceção é igual a `expected_type`.
    - Confirmado: um desses saiu CONFIRMED.

**Divergências entre documentação e código [F]:**
- A doc diz que a LLM "nunca escreve código". O healing escreve stubs e edições.
- A doc diz "mesma exceção na mesma linha". O código compara o tipo da exceção do ESBMC e a linha só no replay, e o replay faz busca em vez de rodar o contraexemplo.
- A doc dá o unwind como fixo, e ele escala.
- A doc não traz LLM_ONLY, BOUND_INCONCLUSIVE, HANDLED_BY_CALLER, DEPENDS_ON_LIBRARY nem o refinamento.
- A doc afirma "0 confirmações falsas no controle", e o controle não rodou em 16/11.

**Implementado mas inativo em 16/11 [F]:**
- variantes A3 e A6 a A22;
- oráculo de valor (A15) e controle nas corrigidas;
- agente de fallback;
- cache de detecção;
- lições automáticas;
- replay aleatório;
- modo scan.

---

## Parte 4. Histórico experimental (resumo)

Detalhe completo: `docs/experimentos/README.md`. Seleção do que importa para a validade:

| Período | O que aconteceu | Por que importa |
|---|---|---|
| 02/09 a 01/10 (F1 a F6) | motor e métricas mudam várias vezes; harness escrito pela LLM é abandonado | não comparável com nada posterior |
| 06/10 (F9) | A0 a A6 testadas na amostra de 50, **uma rodada por variante**; A5 (A1+A2) escolhida | seleção com n=1 e ruído estimado só pela A0 |
| 12 a 20/10 (F11, F21, F27) | A5 reconfirmada nos mesmos 50/48; três repetições dão 22, 23 e 24 | as repetições mostram faixa de ruído de 22 a 26 (cerca de ±2) |
| 13 e 14/10 (F13) | regras do harness escolhidas olhando os alvos do gabarito | ajuste no conjunto de medida |
| 15 a 19/10 (F14, F22) | A5 usada nos 277, que contêm os 50 de seleção; métrica por "união de rodadas" | união infla o número e não vale como resultado |
| 15/10 | entram os 47 da disciplina | |
| 18/10 | sondas de ESBMC e mypy nos 47 | primeiro contato com os 47 |
| 02 e 03/11 | rodadas nos 47 com Claude e Codex; melhorias medidas em casos dos 47 | |
| 06/11 | rodada chamada de "fora da amostra" | não é limpa (ver achado 4) |
| 07 a 11/11 | 4 rodadas nos 47, cada uma com código e ESBMC diferentes; consertos tirados dos erros | exploratórias |
| 08/11 | A2 editado depois de testes nos 47 | A2 vigente em 16/11 |
| 14/11 | regra por função escrita depois de ver 06 a 11/11 | conservadora, mas post hoc em relação ao conjunto |
| 14/11 | rodada de ruído interrompida (28,4 M tokens) | não vale |
| 16/11 | rodada congelada, pré-registrada, completa na 1ª tentativa | melhor dado disponível; rodada única |
| 16/11, 20:37 | `agente-teste-2026-11-16` em 3 dos 47, com `healing.py` não commitado | não registrado em lugar nenhum |

**Contagens [F, subagente, conferidas por amostragem]:**
- Seis tags de congelamento em 14 dias (de `v2-congelado-2026-11` a `11f`).
- Pelo menos 13 mudanças na definição da métrica desde setembro.
- Cerca de 10 decisões de pipeline informadas pelos 47.
- Cerca de 12 decisões informadas pelos conjuntos da V2.

**Matriz de comparabilidade (principais):**

| Comparação | Classe | Motivo |
|---|---|---|
| F4: repair contra resample (3 réplicas cada) | controlada | um fator só, com réplicas |
| ESBMC 8.5.0 contra master (specs gravadas, sem LLM) | controlada | só o ESBMC muda |
| F27: A5 em três repetições | controlada (variância) | mesma configuração |
| F9 e F21: variantes de prompt | parcialmente controlada | n=1 por variante |
| 02/11 Claude contra 03/11 Codex | parcialmente controlada | n=1 e verificação parcial |
| 06/11 contra 07/11 | inválida para inferência causal | ESBMC e código mudam juntos |
| 07, 08, 09 e 11/11 entre si | exploratória | detecção nova, código e ESBMC diferentes a cada vez |
| 09/11 contra 11/11 tratada como "ruído" (PLANO_2026-11-12:234) | inválida como ruído | 54 arquivos de `src` diferentes |
| 11/11 contra 16/11 | inválida para inferência causal | ESBMC, regra de reparo, isolamento e métrica mudam |
| métrica por união de rodadas | inválida | soma de rodadas, não uma medida |

---

## Parte 5. Auditoria metodológica

### 5.1 Dataset dos 47

**Origem [F].** Foram 47 PRs integrados e distintos, em duas rodadas de mineração:
- 1ª rodada: 45 candidatos, com filtro "título indica falha" e "correção de até 30 linhas". **A consulta exata não está registrada.**
- 2ª rodada: `gh search prs` em 60 repositórios, com cerca de 2.300 títulos triados. **A lista dos 60 repositórios não foi encontrada.**

**Viés de seleção [F nos critérios, I no efeito].** Os critérios davam bônus a construções que o ESBMC-Python já cobre (correções #8247 a #8258) e exigiam um harness que isolasse a função. A amostra favorece a ferramenta. O artigo pode dizer isso, mas não pode generalizar para bugs Python em geral.

**Agrupamento [F].**
- São 21 projetos; MAVProxy (7), python-can (5), pymodbus (4), opcua (4) e ros2cli (4) somam 24 de 47.
- Há 6 grupos com o mesmo arquivo-fonte, cerca de 13 itens. Dois pares são da mesma função: pymavlink 1058/1259 e mavproxy 741/989.
- A versão com bug do gps_127 já contém a correção do gps_126.
- A amostra efetiva é menor que 47.

**Concentração dos resultados [F].** As 8 confirmações vêm de 7 projetos: gps (2), mais blinka, dronekit, gpiozero, paho, simpleio e pymodbus (1 cada). Projetos grandes ficaram com 0 confirmações: mavproxy (0/7), python-can (0/5), ros2cli (0/4) e pymavlink (0/3). Nenhum bug de `struct.error` foi confirmado (0/5).

**Rótulos [F].**
- A categoria vem de um único rotulador ("patch_lido") nos 47, sem medida de concordância.
- 13 rótulos de expressão são a linha vizinha do guarda inserido pelo patch.
- Em vários, a expressão rotulada não tem relação com o defeito. Por exemplo, `now = time.time()` em mavproxy_1032, onde o defeito real é `self.master` ser None.
- A ressalva do pymodbus_2980 cita a função irmã errada.
- Os três patches largos ainda não foram revisados por você.

**Contaminação [risco, não prova].** O manifesto não tem datas de merge. Pelo número dos PRs, vários devem ser anteriores a 2021 (paho#118, MiniMQTT#5, SimpleIO#43, gpiozero#716). Isso é **[H]** até consultar as datas.

**Separação desenvolvimento e teste [F].** Não existe. A regra de seleção de um conjunto novo ainda não foi escrita.

### 5.2 Métricas

| Métrica | Numerador / denominador | Problema | Adequada para |
|---|---|---|---|
| Apontado | bugs com hipótese numa função do rótulo / 47 | 47/47 por construção | nada (só apoio) |
| Apontado e reproduzido | bugs com replay do mesmo *tipo* de exceção na função / 47 | ignora a linha; roda no harness com busca própria; inclui hipóteses que o ESBMC não confirmou | "a LLM propôs um cenário que levanta a exceção certa no harness" |
| Confirmado pelo ESBMC | bugs com CONFIRMED entre os reproduzidos / 47 | vale para o harness; o tipo da exceção do ESBMC é comparado como conjunto; 1 de 8 com assinatura alterada | "o par LLM + ESBMC confirma, no harness, a exceção esperada" |
| Vereditos por hipótese | 106 (com duplicata) ou 105 | denominador duplo | descrição do funil |
| LLM_ONLY | hipóteses que o ESBMC nunca aceitou | mistura limite de linguagem (25), erro interno do ESBMC (4), contexto do harness (8), limite de voltas ou tempo contados como "só LLM" (12) e "outro" (15) | precisa ser desdobrada |
| Funil por bug | um estágio por bug | a ordem coloca "recusado" antes de "inconclusivo": 20 e 3 com a ordem do script, 18 e 5 com a ordem inversa | descrição, com a regra de precedência explicada |
| Custo | US$ 42,04 (estimativa reportada pelo CLI; o pagamento foi pela assinatura) | 89% vem da síntese; os tokens incluem leitura de cache | custo por bug confirmado: US$ 5,26 |

**Não podem ser calculados com os dados atuais:**
- **precisão, falso positivo, especificidade:** faltam negativos;
- **recall em relação a bugs reais em geral:** a amostra é de conveniência e enviesada;
- **variância entre execuções da configuração congelada:** só há uma rodada.

**Separação pedida no item 7 da auditoria, por bug, em 16/11 [F, recálculo próprio].** A tabela segue a ordem do script: um bug fica no primeiro estágio que alcança.

| Estágio | Bugs |
|---|---:|
| ESBMC e CPython com a exceção esperada | 8 |
| CPython com a exceção esperada, sem ESBMC | 5 |
| ESBMC confirmou outra exceção | 5 |
| ESBMC achou violação, CPython não validou | 5 |
| ESBMC nunca aceitou nenhuma hipótese do bug, ou ficou em LLM_ONLY | 18 a 20 (depende da precedência) |
| Limite de voltas ou de tempo | 3 a 5 |
| Sem violação | 1 |
| Falha de infraestrutura | 0 (1 timeout de chamada de síntese) |
| Execução interrompida | 0 |

Os dados não separam "a LLM não identificou o defeito" de "a LLM identificou e o harness falhou". Para isso seria preciso comparar a hipótese com o rótulo, e o nível por expressão foi rebaixado justamente porque essa comparação é frágil. A pergunta continua sem resposta.

---

## Parte 6. Auditoria estatística

### 6.1 Intervalos para 16/11

Wilson e Clopper-Pearson a 95%, mais bootstrap por projeto (20 mil reamostras dos 21 projetos):

| Quantidade | k/n | Estimativa | Wilson | Clopper-Pearson | Bootstrap por projeto |
|---|---|---:|---:|---:|---:|
| Apontado e reproduzido | 13/47 | 27,7% | 16,9 a 41,8% | 15,6 a 42,6% | 16,0 a 44,7% |
| Confirmado pelo ESBMC | 8/47 | 17,0% | 8,9 a 30,1% | 7,6 a 30,8% | 6,1 a 33,3% |
| Confirmado, dado reproduzido | 8/13 | 61,5% | 35,5 a 82,3% | 31,6 a 86,1% | |
| Hipóteses CONFIRMED | 13/106 | 12,3% | 7,3 a 19,9% | 6,7 a 20,1% | |
| Hipóteses com veredito do ESBMC | 40/105 | 38,1% | 29,4 a 47,6% | 28,8 a 48,1% | |

**Limitações:**
- Os intervalos supõem bugs independentes, o que não vale: há grupos do mesmo arquivo. O bootstrap por projeto trata parte disso, mas com 21 grupos de tamanhos muito diferentes ele é instável.
- Os intervalos descrevem a variação de amostragem *sob o modelo binomial*. Não dizem a probabilidade de o valor verdadeiro estar no intervalo.
- Eles não incluem a variação do LLM entre execuções, que nunca foi medida na configuração congelada.
- As hipóteses do mesmo bug são dependentes. Os intervalos por hipótese são só descritivos.

### 6.2 Variação entre rodadas (reavaliação com a regra atual)

| Rodada | Resultados com `target_range` | Reproduzidos | Confirmados | Bugs confirmados |
|---|---:|---:|---:|---|
| 06/11 | 25 de 123 | 9 | 6 | blinka, gpiozero, mavproxy_1572, paho, pythoncan_1293, simpleio |
| 07/11 | 27 de 123 | 8 | 5 | blinka, gpiozero, paho, pythoncan_1293, simpleio |
| 09/11 | 41 de 109 | 12 | 8 | blinka, gpiozero, gps_126, mavproxy_1572, paho, pythoncan_1293, ros2cli_1112, simpleio |
| 11/11 | 40 de 116 | 13 | 9 | blinka, dronekit, gpiozero, gps_126, gps_60, mavproxy_1572, paho, pythoncan_1293, simpleio |
| 16/11 | 45 de 106 | 13 | 8 | blinka, dronekit, gpiozero, gps_126, gps_60, paho, pymodbus_2921, simpleio |

**Ressalvas:**
- As rodadas antigas têm menos resultados com `target_range`, porque o esquema do replay mudou. Nelas, a regra que aceita falha fora da expressão não se aplica, então os números antigos podem estar subestimados.
- Nenhuma dessas rodadas é réplica de outra: mudaram código, ESBMC e prompt. Para 07/11, o valor confere com o recálculo do `EXECUCAO_CODEX_2` (8 e 5).

**Leitura [I]:**
- Entre 11/11 e 16/11, que são as rodadas mais parecidas, 3 bugs trocam de estado (2 saem, 1 entra). Um teste de McNemar com 1 contra 2 pares discordantes não tem nenhum poder.
- A detecção, medida pelo nível por linha em 48 casos (F27), varia de 22 a 26 entre repetições iguais.
- Juntando as duas coisas, a variação de uma rodada para outra é da ordem de 2 a 3 bugs.
- Diferenças desse tamanho entre configurações não sustentam a afirmação "melhorou".

### 6.3 O que falta para uma análise estatística defensável

- **Repetições da configuração congelada nos mesmos 47.** Pelo menos 3 rodadas completas, com detecção nova em cada uma, para estimar a variação por bug. A r2 do script reaproveita a detecção e mede só a variação da verificação. As duas variações são úteis, mas respondem a perguntas diferentes.
- **Comparações pareadas por bug.** McNemar exato, ou modelo de efeitos mistos com bug e projeto como efeitos aleatórios, só quando houver repetições.
- **Correção para comparações múltiplas,** se várias variantes forem comparadas no conjunto novo.
- **Um conjunto independente,** porque nenhuma estatística no conjunto de desenvolvimento corrige o viés de otimização.

---

## Parte 7. Auditoria técnica

### 7.1 LLM

- **Modelo e versão [F].** `claude-sonnet-5-5` nas 560 chamadas; uma chamada sem modelo retornado (timeout).
- **Parâmetros [F].** Não há temperatura, top_p nem semente: vale o padrão do CLI. O modelo hospedado pode mudar sem aviso. Não existe identificador de snapshot no registro.
- **Contexto [H].** O tamanho da entrada sugere que algo além do prompt entra na chamada (achado 10).
- **Tentativas [F].** Uma chamada de detecção por função, sem retentativa: as 2 retentativas do perfil são só para falha operacional, e nenhuma foi usada. A síntese fez 507 chamadas para 106 hipóteses, cerca de 4,8 por hipótese.
- **Cache [F].** O cache de detecção estava desligado. O cache de prompt do provedor reduz custo e não muda a resposta.
- **Seleção de prompt [F].** A1+A2 foram escolhidas na amostra de 50 da V2, com uma rodada por variante. A2 foi editado depois, com base em testes nos 47. Nenhuma das duas escolhas foi independente da avaliação.

### 7.2 Harness e ESBMC

- **O que uma confirmação significa [F].** Uma confirmação mostra que existe uma entrada, nas pré-condições do harness, que leva o harness a levantar a exceção esperada. As pré-condições vêm dos tipos que a LLM escolheu, dos atributos gerados e dos stubs não determinísticos. **Não mostra** que essa entrada é alcançável a partir do programa real. A metodologia distingue "violação no modelo" de "bug real" no aviso do relatório, mas a métrica não guarda essa separação.

- **Mudanças de semântica possíveis [F].**
  - O healing pode alterar assinaturas: pymodbus_2921 foi de `bytes` para `str` no programa do ESBMC.
  - O healing pode remover `**kwargs` de construtores (pymodbus_1738, um CONFIRMED de outra exceção) e trocar módulos por stubs (mavproxy_881).
  - O refinamento pode estreitar entradas por assunção.
  - `none_guards` injeta `raise`, mas o CONFIRMED depende do replay no programa sem as reescritas, o que reduz o risco.
  - `cut_after_suspect` é uma subaproximação: pode esconder falhas, mas não cria falso positivo **[I]**.

- **O replay como juiz [F].**
  - É a parte que protege contra falso alarme do ESBMC.
  - Ele roda o *harness*, com os mesmos stubs e as mesmas edições de healing feitas fora do corpo, e não o projeto.
  - Não exige a mesma entrada do ESBMC.
  - O CONFIRMED aceita que o ESBMC tenha listado a exceção entre várias outras, como no pymodbus_2921: "array bounds violated; ... unwinding assertion loop 6; uncaught exception: IndexError".

- **Flags [F, subagente].** Não foram usados `--no-pointer-check --no-align-check`, ao contrário do comentário em `esbmc_runner.py:15-17`. Isso parece coerente com as rodadas de novembro, mas precisa ser registrado.

- **Procedência do ESBMC [F].** Commit `de72a905e0`, sha256 `d9f0de1f...`, `dirty: true` (provavelmente só o `esbmc.sh` não rastreado **[I]**). O `CONGELAMENTO_2026-11-14.md` ainda mostra a tag `11e` e o binário de 14/11. Está desatualizado em relação à rodada de 16/11.

- **Erros internos do ESBMC [F].** 4 hipóteses caíram em `esbmc_crash`, contadas dentro de LLM_ONLY. Elas deveriam ser relatadas à parte, como falha da ferramenta.

---

## Parte 8. Reprodutibilidade

| Requisito | Situação | Evidência |
|---|---|---|
| Versão fixa do código | parcialmente atendido | `commit.txt` = `f086e22`, mas sem `git status`; o resultado de 16/11 e `scripts/relatorio_bugs.py` não estão commitados |
| Tag | parcialmente atendido | a tag `11f` aponta `f55cc5a`, a rodada foi em `f086e22` (diferença só em doc) |
| Configuração experimental | atendido | `config` no JSON e script de execução |
| Identificação do modelo | parcialmente atendido | nome do modelo sim; snapshot e parâmetros de amostragem não |
| Prompts completos | parcialmente atendido | os arquivos de prompt estão no repositório, mas a mensagem completa enviada (com o que o CLI injeta) não é gravada |
| Versão do ESBMC | atendido | commit, sha256 e data do binário |
| Dependências e ambiente | parcialmente atendido | `requirements*.txt`; sem lockfile com hash; WSL e disco externo |
| Sementes | não atendido | LLM sem semente; replay determinístico |
| Logs | atendido | `run.log`, telemetria, programas gerados |
| Resultados brutos | atendido | `v2_verify_report.json`, `v2_checkpoint.json` |
| Scripts de agregação | parcialmente atendido | o avaliador está no código; `relatorio_bugs.py` não está commitado |
| Instruções de execução | atendido | `CONGELAMENTO_2026-11-14.md` (com versão desatualizada) |
| Registro de falhas | atendido | `docs/experimentos/README.md` |
| Custos | atendido | telemetria por chamada |
| Auditoria independente | parcialmente atendido | dataset no repositório; acesso ao Claude CLI com assinatura não se reproduz igual; o binário do ESBMC fica num disco local |

**Dependências que impedem a reprodução exata:** o modelo hospedado e mutável, o CLI do Claude Code e sua versão (não registrada), o contexto que o CLI injeta, e o master do ESBMC compilado localmente.

---

## Parte 9. Ameaças à validade

| Tipo | Ameaça | Gravidade | Corrigível com os dados atuais? |
|---|---|---|---|
| Interna | Pipeline ajustado nos 47 (A2, regra de reparo, regras de harness) | alta | não; precisa de conjunto novo |
| Interna | Mudanças simultâneas entre rodadas (código, ESBMC, métrica) | alta | não; precisa de rodadas controladas |
| Interna | Contexto do CLI possivelmente variável e não registrado | média | não; precisa de teste com uma chamada |
| Construto | "Reproduzido" mede o tipo da exceção no harness, não o bug | alta | sim, em parte: reclassificar exigindo linha ou expressão, como análise de sensibilidade |
| Construto | Confirmação no harness, não no programa | alta | parcial: descrever com cuidado; prova de alcance exige trabalho novo |
| Construto | Healing com troca de tipo (pymodbus_2921) | média | sim: listar e relatar com e sem esses casos |
| Construto | Sem negativos: o nível "apontado" não discrimina | alta | não; precisa de detecção nas funções corrigidas ou em funções sem bug |
| Construto | LLM_ONLY mistura causas diferentes | média | sim: desdobrar com os dados atuais |
| Externa | Amostra enviesada para o que o ESBMC suporta; 21 projetos, IoT/CPS | alta | não; delimitar no texto |
| Externa | Um só modelo de LLM | média | não; outro modelo custa chamadas |
| Conclusão | n=47, rodada única, bugs agrupados | alta | parcial: relatar intervalos; repetições custam chamadas |
| Conclusão | Seleção de prompt com n=1 por variante | média | não, mas pode ser declarada |
| Conclusão | Risco de contaminação (PRs antigos) | média | parcial: datas dos PRs via API, sem custo de LLM |

---

## Parte 10. Contribuições científicas

| Contribuição | Classificação |
|---|---|
| Integração LLM + ESBMC-Python para confirmar hipóteses de bug | implementada e demonstrada no conjunto de desenvolvimento |
| Harness por código a partir de JSON de tipos (a LLM não escreve o driver) | implementada e demonstrada; sem avaliação comparativa |
| Self-healing guiado pelo erro do ESBMC | implementado; efeito não isolado (3 de 13 CONFIRMED passaram por ele; não há rodada sem healing na mesma configuração) |
| Replay no CPython como filtro de falso alarme | implementado; sem medida de quantos alarmes ele barrou de verdade ou de quantos bugs reais ele perdeu |
| Caracterização de limites do ESBMC-Python (recusas, issues abertas) | implementada e demonstrada; é a contribuição mais sólida e independente da LLM |
| Custo por bug confirmado | medido numa rodada |
| Variabilidade do LLM | dados parciais na V2 (F27); não medida nos 47 congelados |
| Grounding por AST | implementado na verificação; não avaliado isoladamente |
| Análise de repositórios reais (scans) | executada, 0 bugs novos confirmados (memória do projeto, **NV** aqui) |

Boa parte disso é contribuição de engenharia. A científica depende de pergunta de pesquisa explícita e comparação controlada. Para falar de novidade, falta uma revisão de trabalhos relacionados que **não foi feita nesta auditoria**.

---

## Parte 11. Parecer de revisor (simulado)

**Pontos fortes:**
- a transparência sobre as limitações;
- a rodada pré-registrada;
- a procedência do ESBMC;
- a separação de níveis na métrica;
- o registro de experimentos detalhado;
- as issues reais abertas no ESBMC.

**Motivos prováveis de rejeição:**
1. Avaliação só no conjunto de desenvolvimento.
2. Ausência de negativos, sem medida de falso positivo.
3. Métrica de "reprodução" baseada só no tipo da exceção, num harness com pré-condições escolhidas pela LLM.
4. Rodada única, sem variância.
5. Sem baseline justo, por exemplo LLM sozinha com replay e sem ESBMC, o que mediria o valor do ESBMC.
6. Amostra pequena e enviesada para o que a ferramenta suporta.
7. Reprodutibilidade dependente de serviço hospedado sem controle de amostragem.

**Corrigível sem experimento novo:** itens 3 (análise de sensibilidade), 6 (delimitar o escopo no texto), parte do 7 (registrar) e a parte de descrição honesta do item 1.

**Exige experimento novo:** itens 1, 2, 4 e 5.

---

## Parte 12. Plano de ação (proposta; as decisões são suas)

Legenda: **[sem LLM]** usa só artefatos e código; **[LLM]** exige chamadas pagas ou de assinatura.

### P0: bloqueadores

1. **Escrever a regra de seleção do conjunto novo antes de olhar bugs** [sem LLM].
   - Itens a definir: fonte, consulta exata, janela de datas posterior ao corte do modelo, critérios de inclusão sem bônus para o que o ESBMC suporta, número-alvo e quem rotula.
   - Critério de pronto: documento commitado com data, antes da primeira consulta.
   - Risco: escrever a regra olhando os candidatos.

2. **Medir falso positivo** [LLM]. A detecção nas funções corrigidas (`scripts/deteccao_corrigidas.sh`) já está preparada. Melhor ainda: incluir funções sem bug do mesmo arquivo no conjunto novo, para o nível "apontado" discriminar.
   - Custo estimável: a detecção de 16/11 custou cerca de US$ 4,44 em 53 chamadas.
   - Critério de pronto: taxa de hipóteses e de CONFIRMED nas versões sem bug.

3. **Testar o que o CLI injeta no contexto** [1 chamada]. Fazer uma chamada isolada com um prompt trivial e comparar `prompt_tokens` com o tamanho esperado. Se houver excesso, descobrir a origem (CLAUDE.md global, hooks) e bloquear. Uma opção é rodar a detecção pela API, com `temperature` registrada.
   - Critério de pronto: o contexto enviado fica documentado e igual em qualquer máquina.

### P1: antes da submissão

4. **Análise de sensibilidade da métrica** [sem LLM]. Recalcular 16/11 com três variantes:
   - (a) só replay `reproduced` na expressão suspeita, sem aceitar `other_failure`;
   - (b) sem os casos com mudança de assinatura pelo healing;
   - (c) exigindo que o ESBMC tenha a exceção como *única* violação, ou a principal.

   Critério de pronto: tabela com 13/8 e as variantes lado a lado.

5. **Desdobrar LLM_ONLY e o funil** [sem LLM]. Separar limite de linguagem, crash do ESBMC, contexto do harness e "outro" (15 casos sem explicação). Fixar e explicar a regra de precedência.

6. **Inventário das mudanças de semântica do healing** [sem LLM]. Para as 66 hipóteses com healing, classificar as edições (assinatura, remoção de parâmetro, stub de módulo, simplificação de corpo).

7. **Repetições da configuração congelada** [LLM].
   - No conjunto novo: pelo menos 3 rodadas completas, com detecção nova.
   - Nos 47: rodar a r2 já prevista no script, para medir só a variação da verificação.
   - Critério de pronto: variação por bug, com intervalo.

8. **Baseline justo** [LLM ou sem LLM, conforme a variante]. A pergunta é quanto o ESBMC acrescenta. Comparar:
   - LLM + replay sem ESBMC: com os dados atuais já dá para estimar o nível "reproduzido", que é 13;
   - pipeline completo: 8;
   - mypy e pytest na mesma unidade de contagem.

   Risco: o replay sozinho pode parecer melhor que o pipeline. Isso também é resultado.

9. **Datas dos PRs** [sem LLM, API do GitHub]. Para quantificar o risco de contaminação e separar "antes" de "depois" do corte do modelo.

10. **Corrigir o dataset** [sem LLM]. Ressalva do pymodbus_2980, revisão dos três patches largos, chave `crash_expressions` ausente em 29 itens.

### P2: recomendadas

11. Gravar `git status`, a versão do Claude CLI e o prompt completo enviado, por chamada.
12. Atualizar `entendendo_o_pipeline.md` e `CONGELAMENTO_2026-11-14.md`.
13. Commitar o resultado de 16/11 e `scripts/relatorio_bugs.py`, e registrar a rodada `agente-teste-2026-11-16`.
14. Tratar a duplicata de hipótese (106 contra 105).
15. Segundo rotulador numa amostra dos rótulos, com medida de concordância.

### P3: trabalhos futuros

16. Prova de alcance pelo programa real (chamadores, sem stubs).
17. Comparação entre modelos.
18. Ablação do healing e do refinamento.
19. Análise de repositórios sem bug conhecido (scan), com triagem humana.

---

## Parte 13. Perguntas ainda sem resposta

1. O que entra de fato no contexto da chamada `claude -p` isolada (cerca de 36 mil tokens)?
2. Quantos dos 13 "reproduzidos" levantam a exceção na mesma expressão que o patch corrige? A resposta exige cruzar a linha do replay com o rótulo, que está em coordenadas do harness.
3. Das 8 confirmações, em quantas a pré-condição do harness (por exemplo, `_pwmpin` None no blinka_434) é alcançável no projeto real?
4. Quanto o healing contribui? Não há rodada sem healing na mesma configuração.
5. Qual a variação da verificação sozinha (a r2 que reaproveita a detecção)?
6. Quais são as datas dos 47 PRs?
7. Por que 15 hipóteses caem em LLM_ONLY com motivo "other"?
8. Qual foi o objetivo e o resultado da rodada `agente-teste-2026-11-16`?
9. O commit do ESBMC em 11/11: `b1b4d6ccf9` (cronologia) ou "não registrado" (tabela do artigo)?

---

## Parte 14. Conclusões permitidas e proibidas

### Sustentadas pelas evidências

- Numa rodada pré-registrada, com o pipeline congelado, sobre um conjunto de desenvolvimento de 47 bugs reais de 21 projetos Python de CPS e IoT:
  - o pipeline produziu, para 13 bugs, um cenário que levanta no harness a exceção do rótulo;
  - em 8 deles, o ESBMC confirmou a mesma exceção (17%, IC 95% de Wilson de 9% a 30%).
- O ESBMC chegou a veredito em 40 de 105 hipóteses. A maior parte das perdas vem de construções que o frontend Python não aceita.
- O custo dessa rodada foi de cerca de US$ 42 em valor de API (US$ 5,26 por bug confirmado), e a síntese do harness respondeu por 89%.
- Entre rodadas de configuração parecida, o conjunto de bugs confirmados muda em 2 a 3 casos.
- O trabalho identificou limitações concretas do ESBMC-Python e as relatou como issues.

### Não sustentadas com os dados atuais

- Que o pipeline "localiza" bugs, ou qualquer número de precisão, recall, especificidade ou falso positivo.
- Que os resultados valem fora do conjunto de desenvolvimento, ou que a rodada de 06/11 foi "fora da amostra".
- Que uma mudança (prompt, healing, regra de reparo, versão do ESBMC) melhorou o resultado.
- Que os 8 bugs confirmados são alcançáveis no programa real com as entradas encontradas.
- Que o pipeline supera mypy, testes ou LLM sozinha.
- Que o resultado se repete em outra execução ou com outro modelo.
- Que a LLM não conhecia os bugs (risco de contaminação não quantificado).
- Qualquer afirmação de novidade sem revisão de trabalhos relacionados.

---

## Erros dos subagentes, corrigidos

- O subagente do dataset disse que a rodada de 16/11 estava "em andamento". Ela terminou com saída 0 às 17:51.
- O subagente de arquitetura citou o pymodbus_2921 como troca de `bytes` por `bytearray`. A troca final, a que resultou em CONFIRMED, foi para `str` (rodada 3 do healing).
- O subagente de histórico disse que não existiam contagens pela regra nova para 08 a 11/11. Elas foram calculadas nesta auditoria (Parte 6.2), com a ressalva do esquema do replay.
