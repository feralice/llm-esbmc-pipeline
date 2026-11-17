# Consolidação final: plano único para a entrega de CPS e para o mestrado (16/11/2026)

Documento de trabalho da Fernanda. Não é texto para o professor, para o Lucas nem para a banca.

## Como este documento foi feito

- **Autoria e ferramenta.** Escrito pelo Claude Code (Opus 5.5) a pedido da Fernanda, como coordenação das oito auditorias de 16/11. Tudo aqui é organização de evidência e proposta de plano. As decisões científicas (perguntas, título, escopo, interpretação) são dela.
- **Modo.** Só leitura. Não rodei pipeline, ESBMC, testes nem LLM. A única escrita no repositório é este arquivo. Os scripts de conferência ficaram no rascunho da sessão (`/tmp/claude-1000/-home-fernanda-mestrado-llm-esbmc/fd7a2316-c270-40e8-bfa8-1fc8127162f2/scratchpad/rounds.py`, `sens.py`, `cost.py`) e só leem JSON.
- **Entradas lidas inteiras:** as oito auditorias de 16/11, `artigo.tex`, `mapa_dados.md`, `tabela_experimentos.md`, `tabela_scans.md`, `REGRA_DE_ACERTO_2026-11-14.md`, `CONGELAMENTO_2026-11-14.md`, `docs/escrita/revisar-escrita-academica/SKILL.md`. Também consultei, em parte, `docs/pgene601/proposta_projeto_cps_2026-09-22.md`, `trabalhos_relacionados_2026-10-16.md`, o protocolo do guia de escrita (`references/diretrizes-integral.txt`, l. 156-168) e o diff não commitado.
- **Conferências que eu mesma refiz no bruto** (marcadas [F, conferido aqui]): reavaliação das seis rodadas dos 47 pela regra atual; interseção dos confirmados; exclusões das variantes (b) e (d) da sensibilidade; custos de 11/11 e 16/11; nome `error` de `struct.error`; assinatura do pymodbus_2921 nos dois programas; inexistência de `RECUSAS_ESBMC.md`; `artifacts/` no `.gitignore`.

**Siglas das fontes.** AP = `auditoria_pipeline_2026-11-16.md`; A0 a A6 = `auditoria_0_...` a `auditoria_6_...`. "§" indica seção ou parte. Caminhos sem pasta são de `docs/audits/`.

**Rótulos.** [F] fato verificado; [I] inferência; [H] hipótese a testar; [NV] não verificado.

**Suposição de tempo (você ajusta).** Cerca de 2 h por dia útil e 5 a 6 h por dia de fim de semana. De 17/11 a 30/11 isso dá 10 dias úteis (20 h) e 4 dias de fim de semana (cerca de 22 h): **cerca de 42 h no total**. O dia 20/11 (sexta) é feriado nacional da Consciência Negra; se for folga para você, ganha umas horas, mas o cronograma não conta com isso [NV].

---

## 1. Diagnóstico consolidado (Etapa 1)

### 1.1 Em oito frases

1. A rodada de 16/11 é o melhor dado que existe: pré-registrada, completa na primeira tentativa, com 13/47 bugs reproduzidos no CPython e 8/47 confirmados pelo ESBMC [F, AP §1 item 1; conferido aqui].
2. Ela é uma medida em **conjunto de desenvolvimento**: os 47 moldaram prompt, harness e regra de reparo até horas antes da rodada [F, AP achado 4; A5 §6].
3. O nível "apontado" vale 47/47 por construção e não existem negativos, então precisão, falso positivo e localização não podem ser medidos [F, AP achado 5; A2 §3.1].
4. A confirmação vale **para o harness**, não para o programa real: casca de `__init__`, stubs, `none_guards`, `cut_after_suspect`, e um caso em que o ESBMC verificou outra assinatura (pymodbus_2921) [F, AP §7.2; A4 §2, §9].
5. O número 8 é frágil sob critérios mais estritos: o núcleo que resiste às variantes razoáveis tem 4 bugs [F, A4 §11; exclusões conferidas aqui].
6. O conjunto confirmado muda 2 a 3 bugs entre rodadas próximas, mas nenhuma rodada é réplica de outra [F, AP §6.2; A5 §3, §5].
7. A maior parte das perdas vem do frontend Python do ESBMC (32 a 39 das 65 hipóteses sem veredito), e isso é uma contribuição que não depende da LLM [I, A4 §12].
8. Para a disciplina, **nada disso exige experimento novo**: exige reanálise sem LLM dos JSON existentes, texto honesto e referências conferidas [I, seções 2 e 7 abaixo].

### 1.2 Problemas, um por linha

Legenda. Gravidade: **A** alta, **M** média, **B** baixa (para o artigo de CPS). Esforço: **P** até 1 h, **M** 1 a 3 h, **G** mais de 3 h. Custo: US$ só quando há chamada de LLM. "Sem LLM?" diz se dá para resolver (ou declarar com honestidade) sem chamar modelo.

| ID | Problema | Evidência (origem) | Impacto científico | Impacto técnico | Grav. | Esforço | Custo | Depende de | Sem LLM? |
|---|---|---|---|---|---|---|---|---|---|
| P01 | Os 47 são conjunto de desenvolvimento | AP achado 4; A5 §6 (A2 editado em 08/11, regra de reparo de 16/11, `fdf7178` 3 h antes) | resultado otimista; sem generalização | nenhum | A | P (declarar) | 0 | nada | sim, para declarar; resolver só com conjunto novo (mestrado) |
| P02 | Sem negativos; "apontado" 47/47 por construção | AP achado 5; A2 §3.1; `REGRA_DE_ACERTO` | sem precisão, falso positivo, localização | `fp` e `precision` gravados nos JSON são enganosos (A5 achado 6) | A | P (declarar) | 0 | nada | sim, para declarar |
| P03 | "Reproduzido" aceita a exceção do tipo certo em qualquer linha da função; 2 dos 13 vêm de stub | A2 §3.2 e §4.2; A4 §11 (a); A5 achado 4 | construto inflado no nível intermediário | avaliador `v2_evaluator.py:279-289` | M | P | 0 | nada | sim: relatar 13 e 11 lado a lado |
| P04 | Teto de 42: `struct.error` nunca casa (replay grava `error`; stub de `struct` não levanta) | A2 §4.1; `python3 -c` imprime `error` [F, conferido aqui] | denominador com 5 bugs impossíveis | `replay_worker.py:250` | M | P | 0 | nada | sim |
| P05 | Dois "8 de 47" com conjuntos diferentes | A2 §3.2 e §4.4 | risco de citar o número errado | `report.py:69-77` não exige tipo | M | P | 0 | nada | sim |
| P06 | pymodbus_2921: ESBMC verificou `data: str`, replay rodou `data: bytes` | A4 §9; `programs/8432febfbe95_a0.py:22` contra `_a0_replay.py:22` [F, conferido aqui] | uma das 8 provas é sobre outro programa | `preservation.py:321-326` ignora a assinatura | A | P | 0 | nada | sim: sensibilidade (b) |
| P07 | Confirmação vale para o harness; blinka_434 prova a guarda injetada; mavproxy_881 usa estado irreal | AP §7.2; A2 §1.3; A4 §2, §9 | nenhuma confirmação mostra alcance real | casca, stubs, `none_guards` | A | M (descrever) | 0 | nada | sim, para declarar; alcance real é mestrado |
| P08 | Replay quase nunca usa o contraexemplo (12 de 13) | A4 §7 | "mesma entrada" não pode ser dito | `seeds_only` existe mas não decide | M | P | 0 | nada | sim |
| P09 | Rodada única; 2 a 3 bugs mudam entre rodadas; 15 a 25% das hipóteses iguais mudam de veredito | AP §6.2; A5 §3.2, §5.1 | sem variância da configuração congelada | r2 prevista em `rodar_47_ruido.sh` | A | P (declarar) | r2: US$ 37,61 a 136,80 (A5 §12) | cota | declarar sim; medir não |
| P10 | Baselines em unidades diferentes; sem LLM sozinha nem pipeline sem ESBMC | AP achado 9; A5 §9 | comparação injusta se posta numa linha só | nenhum | M | M | 0 | nada | sim: tabela por unidade |
| P11 | LLM_ONLY mistura causas; 4 `Unsupported:` contados como violação | AP §5.2; A4 §12 | funil mal explicado | categorias `other`, regex `_INTERNAL` | M | M | 0 | nada | sim |
| P12 | Funil por bug depende da ordem de precedência (18 a 20 "recusados") | AP §5.2; `scripts/relatorio_bugs.py` (não commitado) | número muda com a regra | script fora do git | B | P | 0 | nada | sim |
| P13 | Contexto do `claude -p` pode trazer CLAUDE.md global e hooks (~36 mil tokens por detecção) | AP achado 10; A5 achado 7 (60,9 mil para 36,6 mil com o modo isolado) | entrada não reproduzível fora desta máquina | `cli_args.py:255-259` | M | P | US$ 0,08 (1 chamada) | sua autorização | declarar sim; testar exige 1 chamada |
| P14 | Sem temperatura, semente nem snapshot do modelo | AP §7.1 | reprodução exata impossível | `claude_cli.py:27-42` | M | P | 0 | nada | sim (declarar) |
| P15 | Artefatos frágeis: `artifacts/` no `.gitignore`; `relatorio_bugs.py` fora do git; binários antigos do ESBMC perdidos; `~/esbmc-master` já avançou | A5 §7.1 e achado 8; AP §8; `git check-ignore artifacts` [F, conferido aqui] | reprodutibilidade fraca | risco de perder a rodada de 16/11 | M | P | 0 | sua decisão sobre como guardar | sim |
| P16 | Documentos desatualizados ou contraditórios | A0 §10 (16 itens); `mapa_dados.md` e `tabela_experimentos.md` dizem "em andamento" para 16/11 | o texto pode herdar erro | nenhum | M | M | 0 | nada | sim |
| P17 | Gabarito com rotulador único, 13 rótulos vizinhos do guarda, ressalva do pymodbus_2980 errada, `crash_expressions` ausente em 29, sem datas | AP §5.1; A2 §2.5, §2.6; A0 §3 | erro de rótulo não medido | manifesto | M | M | 0 | nada | sim (declarar; corrigir ressalva) |
| P18 | Comparador de expressões erra nos dois sentidos | A2 §4.3 | só afeta o nível de apoio | `v2_evaluator.py:56-85` | B | G | 0 | nada | sim, mas fica para o mestrado |
| P19 | Contaminação possível (PRs antigos; sem `merged_at`) | AP §5.1 [H]; `REGRA_DE_ACERTO` | memória do modelo não descartada | manifesto | M | P a M | 0 (API do GitHub) | rede | sim |
| P20 | Seleção dos 47 dava bônus ao que o ESBMC suporta | AP §5.1 | generalização indevida | nenhum | A | P (declarar) | 0 | nada | sim |
| P21 | Scan: 35 CONFIRMED brutos, só 13 triados; 22 sem triagem (Amazon); rodadas de 13 e 14/11 fora do README; regra de veredito do agente diferente | A3 §1, §7, §3.10 | nenhum bug novo pelo ESBMC; sem precisão | procedência incompleta no `scan_report.json` | M | M | 0 | nada | sim |
| P22 | A proposta da disciplina pedia comparar a taxa no corpus CPS com a do corpus geral e fazer ablação de pré-condição | `proposta_projeto_cps_2026-09-22.md` (seções "Pergunta" e "Método"); A1 §8 (regra atual não se aplica ao BugsInPy sem `expected_type`); A6 §1.4 (`ablation.py` saiu do código) | a pergunta original não é respondível de forma defensável [I] | nenhum | A | P | 0 | conversa com o professor, se ela achar necessário | sim: declarar a mudança de pergunta |
| P23 | Rodada `agente-teste-2026-11-16` sem registro, com `healing.py` não commitado | A5 achado 10; `git status` | nenhum para o artigo | estado `running` | B | P | 0 | sua decisão | sim |
| P24 | Referências do repositório com metadados divergentes (DOI do ESBMC-Python, autores de Tihanyi et al., ano de Shivaji et al.) | A6 §3; `trabalhos_relacionados_2026-10-16.md` | citação errada na entrega | `.bib` não existe | A | M | 0 | acesso a DBLP/Crossref | sim |
| P25 | Declaração de IA e protocolo do guia (laudos de 2 ou mais ferramentas, links de todas as referências) | `SKILL.md`; `diretrizes-integral.txt:156-168` | exigência do orientador | nenhum | A | P a M | 0 | ferramentas de laudo (fora do repositório) | sim |

### 1.3 Contradições e correções: resolução

| # | O que estava escrito | O que os dados mostram | Resolução | Situação |
|---|---|---|---|---|
| 1 | `docs/experimentos/README.md` (diff não commitado, l. 1820) cita `possiveis_problemas/disciplina_pgene601/RECUSAS_ESBMC.md` | o arquivo não existe, nem no histórico [F, conferido aqui: `find` e `git log --all`] | **Erro da A0 (§12 item 6) e da A6 (§2.1 item 4, que herdou da A0).** Correção ao enunciado da tarefa: a AP **não** cita esse arquivo (grep sem ocorrência). A A4 §13 já tinha apontado a ausência. Opções: criar o arquivo a partir de `RELATORIO_BUGS.md` ou tirar a citação do README | resolvida; ação pendente (sua escolha) |
| 2 | AP §6.2 chama de "09/11" uma linha com 12 reproduzidos e 8 confirmados | essa linha é a pasta `rodada-final-2026-11-09`; a pasta `rodada-final-2026-11-08` (terminou em 09/11) dá 12 e 9 [F, conferido aqui] | usar os nomes de pasta, nunca só a data. Seis rodadas completas: 06/11 6, 07/11 5, 08/11 9, 09/11 8, 11/11 9, 16/11 8 confirmados | resolvida |
| 3 | AP §1 item 7 e A4 §9 | healing no pymodbus_2921: retorno removido, `bytes` para `bytearray` para `bytes` para `str`; ESBMC viu `data: str`, replay viu `data: bytes` [F, conferido aqui nos dois programas] | o subagente da AP errou ao dizer só `bytearray` (corrigido na própria AP). Relatar com e sem esse caso | resolvida |
| 4 | `REGRA_DE_ACERTO` usa `struct.error` como exemplo de `expected_type` | `struct.error.__name__` é `error` [F, conferido aqui]; o stub de `struct` também não levanta (A2 §4.1) | teto real de "reproduzido" é **42**, não 47. Mostrar as duas bases (47 e 42) e deixar claro qual é a principal | resolvida; decisão sua sobre o denominador principal |
| 5 | "8 de 47" | `by_function.confirmado_esbmc` = 8 (inclui gps_126) e `confirmed_by_location.expression_equivalent.tp` = 8 (inclui pymodbus_2980, exclui gps_126) [F, A2 §3.2; as duas contagens conferidas aqui] | no artigo, só o primeiro é a métrica; o segundo, se aparecer, vai com o conjunto listado | resolvida |
| 6 | O enunciado da tarefa diz que o núcleo de sensibilidade (b, c, d juntas) são "os mesmos 4 estáveis em todas as rodadas" | **não são os mesmos.** Núcleo da sensibilidade: gps_60, gpiozero_716, paho_118, simpleio_43 (A4 §11). Núcleo estável nas seis rodadas: blinka_434, gpiozero_716, paho_118, simpleio_43 [F, conferido aqui: interseção dos seis relatórios; também A5 §5.1, §11.1]. gps_60 só foi confirmado em 11 e 16/11; blinka_434 cai na variante (d) por ter `Optional` na especificação [F, conferido aqui] | usar três números distintos: 4 (sensibilidade), 4 (estáveis), **3 nos dois** (gpiozero_716, paho_118, simpleio_43) | resolvida |
| 7 | Custos: 16/11 US$ 42,04 em 560 chamadas; 11/11 US$ 145,08 em 1109 chamadas | [F, conferido aqui na telemetria]. Tokens antes de 11/11 subcontados (A5 achado 1). A5 §12 estima "pacote mínimo" de US$ 79,74 a 281,88; A6 §6.5 estima "cerca de US$ 80" | **são pacotes diferentes que somam parecido.** A5 = r2 + r3 (só verificação, 2 × 37,61) + detecção nas corrigidas (4,44) + teste de contexto (0,08). A6 = teste de contexto (0,08) + detecção nas corrigidas (4,4) + verificação nas corrigidas (~38) + r2 (~38). As duas usam a base A (16/11). A base B (11/11) multiplica por cerca de 3,5. A A6 inclui um passo (verificação nas corrigidas) que o script atual talvez nem rode: `preparar_deteccao_corrigidas.py` só chama a etapa `detection` (A6 §1.4, [NV] se roda). Pela assinatura não há cobrança, mas há cota (14/11 estourou 6 vezes); pela API o valor vira cobrança contra os US$ 100 | resolvida. **Para 30/11 a recomendação é gastar US$ 0** (seção 7) |
| 8 | `entendendo_o_pipeline.md:312`: "0 confirmações falsas nas versões corrigidas (2 rodadas)" | `control-fixed-2026-10-06` teve 1 CONFIRMED na corrigida (ir_real_03) [F, `docs/experimentos/README.md:145`, `:235`]; no pipeline de 16/11 o controle não rodou | a frase não pode entrar no artigo. Se citar controle, dizer "V2, motor antigo, 1 confirmação na versão corrigida" | resolvida |
| 9 | A6 foi escrita antes de A2 a A5 | A2 a A5 já respondem parte das RQs da A6 | ver tabela 2.3: RQ1 e RQ2 da A6 dependem de negativos (mestrado); RQ3 da A6 já tem piloto com os dados atuais (A2 §3.2, A4 §9 e §11); RQ4 só como exploratória (A5 §5.1); H5 da A6 tem dados prontos (A4 §12) | resolvida |
| 10 | A3: 35 CONFIRMED no scan, 13 triados (11 não bug, 2 bug já conhecido) | a A0 §12 diz "10 CONFIRMED triados" e a A6 §1.1 diz "5 de 5 eram falsos" | **valem os números da A3**, a mais detalhada. A frase da A6 está errada para o pynmea2, que era bug real já conhecido (PR #189). Correção menor na A3: os 22 sem triagem são da Amazon, mas não só de 13 e 14/11; pela própria tabela da A3 §6.2 e §7, incluem `rotation_haiku_lote1` e `sdk_examples_lote1`, de 11/11 [F na tabela da A3; NV no bruto] | resolvida |
| 11 | AP e relatório: `esbmc_crash` = 4; A4: erro interno = 5 | a A4 reclassificou "Unexpected type in int/ptr typecast" de `other` para erro interno [I, A4 §12] | as duas valem; dizer qual (categoria do relatório ou leitura das mensagens) | resolvida |
| 12 | AP: "pelo menos 13 mudanças de métrica"; A5 §4: 19 mudanças de definição ou critério | a A5 lista uma a uma | usar a contagem da A5, com a fonte | resolvida |
| 13 | AP §12 P2.13 e A0 §13: "commitar o resultado de 16/11" | `artifacts/` está no `.gitignore` [F, conferido aqui] | "commitar" exige decisão: copiar resumos (`RELATORIO_BUGS.md`, `avaliacao_funcoes.md`, `commit.txt`) para `docs/experimentos/`, ou guardar um `.tar` com sha256 fora do caminho do build | pendente (sua decisão) |
| 14 | `mapa_dados.md` e `tabela_experimentos.md`: 16/11 "em andamento"; 06/11 "única fora da amostra" | a rodada terminou às 17:51 (A5 §8.1); 06/11 não é limpa (AP achado 4) | corrigir os dois arquivos antes de escrever Resultados | pendente (ação de 18/11) |
| 15 | `artigo.tex`: "47 bugs de 20 projetos"; "gabarito pela linha; níveis expressão, função, arquivo" | 21 projetos; regra por função em dois níveis desde 14/11 (A0 §8) | corrigir os comentários | pendente (ação de 18/11) |
| 16 | Proposta da disciplina (22/09): 5 a 10 bugs, comparação com o corpus geral, ablação de pré-condição | 47 bugs, sem comparação defensável, sem ablação (P22) | declarar no artigo que a pergunta mudou e por quê; se você achar necessário, avisar o professor | pendente (sua decisão) |

---

## 2. Escopo mínimo defensável até 30/11 (Etapa 2)

Tudo nesta seção é **proposta** para você decidir. Onde recomendo uma opção, digo o motivo.

### 2.1 Título provisório (opções)

1. "Hipóteses de LLM verificadas com ESBMC-Python em bugs reais de software Python ciberfísico: um estudo exploratório"
2. "Da hipótese à evidência executável: LLM e verificação limitada de modelos em 47 bugs reais de Python para CPS e IoT"
3. "Onde a verificação de hipóteses de LLM com ESBMC-Python para: funil de 47 bugs reais de sistemas ciberfísicos"

**Recomendação: opção 1.** A palavra "exploratório" já avisa que é conjunto de desenvolvimento, e o título não promete detecção nem localização (P01, P02). A opção 3 é boa se você decidir que o centro do artigo é o funil e os limites do ESBMC.

### 2.2 Problema e objetivo (para você reescrever com suas palavras)

- **Problema, em termos simples:** uma LLM sugere que uma função Python pode quebrar com uma exceção, mas essa sugestão pode estar errada. Como transformar a sugestão em evidência que se possa conferir? [I, A6 §1.1]
- **Objetivo possível:** descrever, numa rodada pré-registrada sobre 47 bugs reais de projetos CPS e IoT, até onde um pipeline LLM + ESBMC-Python + CPython consegue levar cada hipótese, o que uma confirmação significa e onde o processo para.
- **Fora do objetivo:** medir precisão, localizar bugs sem ajuda, provar o bug no programa real, comparar com o corpus geral da proposta (P22).

### 2.3 Perguntas de pesquisa (proposta, com a ponte para a A6)

| RQ proposta para CPS | Responde com | Ponte com a A6 | Por que cabe até 30/11 |
|---|---|---|---|
| **RQ1.** Em quantos dos 47 bugs o pipeline produz evidência da exceção esperada, em cada nível (reproduzido no CPython; confirmado pelo ESBMC)? | 16/11: 13 e 8; intervalos de Wilson (AP §6.1) | parte descritiva da RQ2 da A6, sem afirmar o valor do ESBMC | dado pronto |
| **RQ2.** O que uma confirmação significa e quanto o resultado resiste a critérios mais estritos? | sensibilidade (A4 §11, A5 achado 4), fidelidade ao rótulo (A2 §3.2), risco caso a caso (A4 §9) | é o **piloto da RQ3 da A6**, com um só anotador (você) | só reanálise |
| **RQ3.** Em que etapa as hipóteses e os bugs param, e quais limites do ESBMC-Python explicam as perdas? | funil por bug (`RELATORIO_BUGS.md`), taxonomia (A4 §12), issues | é a **H5 da A6** | só reanálise |
| RQ4 (opcional). Quanto o conjunto confirmado muda entre rodadas de configurações próximas? | A5 §5.1 e §3.2 | **versão exploratória da RQ4 da A6**; nunca como réplicas | dado pronto, mas exige texto cuidadoso; é o primeiro corte se faltar tempo |

**Ficam para o mestrado:** RQ1 e RQ2 da A6 (discriminar com e sem defeito; valor do ESBMC sobre LLM + replay), porque exigem negativos e um braço sem ESBMC rodado à parte (A6 §4; A5 §9.3).

**Recomendação:** RQ1 a RQ3, e RQ4 só se sobrar tempo até 25/11. Motivo: as três se apoiam em dados prontos e reanálise sem LLM, e juntas dão um artigo coerente ("quanto, quão sólido, onde para").

### 2.4 Arquitetura a apresentar

Os passos reais do perfil `congelado`, com quem decide cada um [F, AP §3; A4 §1; A0 §2]:

| Passo | Quem | O que dizer no artigo | O que não dizer |
|---|---|---|---|
| 1. Entrada | dataset | função já recortada (1 ou 2 por arquivo, 53 no total) | que a LLM localiza a função |
| 2. Detecção | LLM (`claude-sonnet-5-5`, prompt A1+A2) | 1 chamada por função; função renomeada, sem docstring | parâmetros de amostragem (não há) |
| 3. Triagem | LLM | campo `verifiable`; 122 achados, 106 enviados | |
| 4. Grounding por AST | código | confere que a expressão citada existe na função | que localiza o defeito (A2 §1.5) |
| 5. Especificação | LLM (só JSON de tipos, stubs, assunções) | o harness é montado por código | que a LLM nunca escreve código (o healing escreve stubs e edições) |
| 6. Montagem e reescritas | código | casca do `__init__`, stubs, `cut_after_suspect`, `none_guards` | |
| 7. ESBMC | código | `--unwind 5 --multi-property` com escalonamento de unwind, solver e tempo; binário cru, sem `--no-pointer-check --no-align-check` | unwind fixo |
| 8. Self-healing | LLM | só quando o ESBMC recusa; até 3 por obstáculo, 9 no total; para se a mensagem não muda | que preserva a semântica (P06) |
| 9. Replay no CPython | código | busca determinística em domínios pequenos, no harness | que reexecuta o contraexemplo |
| 10. Refinamento | LLM | assunção nova quando o replay falha fora da suspeita (até 2) | |
| 11. Veredito e avaliação | código | CONFIRMED = violação + replay na suspeita + tipo entre os do ESBMC; avaliação por função contra `expected_type` | "mesma exceção na mesma linha" |

### 2.5 Datasets

- **Principal:** os 47 da disciplina (21 projetos, 47 PRs, 53 funções; `dataset/disciplina_pgene601/manifest.json`, `docs/projeto/ORIGEM_DOS_47_BUGS.md`) [F, A0 §3].
- **Contexto, uma ou duas frases:** BugsInPy usado no desenvolvimento; 64% dos seus bugs são de valor errado, o que motiva o recorte em exceções (A1 §11) [F].
- **Opcional e curto:** scans em três bibliotecas CPS (Adafruit GPS, pynmea2, pyserial) como relato exploratório de falso positivo, sem precisão (A3 §9). As rodadas da Amazon ficam fora, porque não são CPS e 22 CONFIRMED não foram triados.

### 2.6 Experimentos aproveitáveis

| Experimento | Pasta | Como entra | Fonte |
|---|---|---|---|
| Rodada pré-registrada | `artifacts/pgene601/congelado-2026-11-16-r1/` | resultado principal | AP §1; A5 D16 |
| Seis rodadas completas (06 a 16/11) | `congelado-c-2026-11-06`, `ajustes-2026-11-07`, `rodada-final-2026-11-08`, `rodada-final-2026-11-09`, `rodada-2026-11-11`, `congelado-2026-11-16-r1` | só RQ4 exploratória; nunca como réplicas | A5 §5.1 |
| Baselines mypy e pytest | `mypy-2026-11-03`, `pytest-2026-11-03` | contexto, cada um na sua unidade | A5 §9 |
| Variação da detecção na V2 (22 a 26 em 48) | `artifacts/v2/det-2026-10-20-sc*` | uma frase de contexto sobre ruído | A1 §7; A5 E22 |
| Scans CPS | `artifacts/cps/gps/`, `artifacts/cps/pynmea2/`, `artifacts/scan_pyserial_2026-11-10/` | opcional | A3 §6.1 |

### 2.7 Métricas defensáveis (números já conferidos)

| Métrica | Valor | Intervalo de Wilson 95% | Fonte |
|---|---|---|---|
| Reproduzido no CPython, regra oficial | 13/47 = 27,7% | 16,9 a 41,8% | AP §6.1 |
| Reproduzido, replay estrito (variante a) | 11/47 = 23,4% | 13,6 a 37,2% | A4 §11; A5 achado 4; intervalo calculado aqui |
| Confirmado pelo ESBMC, regra oficial | 8/47 = 17,0% | 8,9 a 30,1% | AP §6.1 |
| As mesmas, sobre o teto de 42 | 13/42 = 31,0%; 11/42 = 26,2%; 8/42 = 19,0% | 19,1 a 46,0%; 15,3 a 41,1%; 10,0 a 33,3% | calculado aqui [F]; teto da A2 §4.1 |
| Núcleo da sensibilidade (b + c1 + c2 + d) | 4/47 = 8,5% | 3,4 a 19,9% | A4 §11; exclusões conferidas aqui |
| Núcleo estável nas seis rodadas | 4 bugs (blinka_434, gpiozero_716, paho_118, simpleio_43) | não se aplica (não são réplicas) | A5 §5.1; conferido aqui |
| Nos dois núcleos | 3 bugs | não se aplica | conferido aqui |
| Hipóteses com veredito do ESBMC | 40/105 = 38,1% | 29,4 a 47,6% | AP §6.1 |
| Funil por bug | 8, 5, 5, 5, 20, 3, 1 (com a regra de precedência explicada) | | `RELATORIO_BUGS.md`; AP §5.2 |
| Fidelidade dos 8 | 5 na expressão do patch; 2 no ponto de estouro em outra função; 1 na linha certa com texto diferente | | A2 §8 |
| Risco dos 8 (leitura caso a caso, um anotador) | 6 baixo, 1 médio (blinka_434), 1 alto (pymodbus_2921) | | A4 §9 [I] |
| Custo | 560 chamadas, 11,45 M tokens, US$ 42,04 em valor de API pela assinatura; 89% na síntese; US$ 5,26 por bug confirmado | | AP §5.2; A5 §8.1; conferido aqui |
| Baselines | mypy 2/47 e 5/47; testes do PR 10 de 11 com teste, 36 sem teste | | A5 §9.1 |

**Sensibilidade completa para a tabela (A4 §11):** oficial 13 e 8; (a) 11 e 8; (b) 7; (c1) 7; (c2) 7; (c3) 4; (d) 5; (d') 6; b + c1 + c2 + d: 4. A variante (c3) é dura demais para BMC e entra só como informação (A4 §11, leitura). **Fixar quais variantes entram antes de escrever Resultados** (A4 §16 item 8), para não escolher pelo número.

**Não defensáveis agora:** precisão, recall, F1, `fp` dos relatórios, "localiza", "fora da amostra", "melhorou", "prova o bug no código real", "mesma entrada no ESBMC e no CPython", qualquer comparação com o corpus geral (AP §14; A2 §8; A5 §11.2).

### 2.8 Figuras e tabelas indispensáveis

Lista detalhada na seção 6. O mínimo: **F1** arquitetura; **T1** dataset; **T2** resultado por nível com sensibilidade; **T3** funil por bug; **T4** taxonomia das perdas; **T5** baselines por unidade.

### 2.9 Limitações obrigatórias no texto

- conjunto de desenvolvimento, ajustado nos mesmos 47 (P01);
- ausência de negativos, sem precisão nem falso positivo (P02);
- confirmação no harness, não no programa real, com os exemplos blinka_434, mavproxy_881 e pymodbus_2921 (P06, P07);
- replay por busca própria, não pelo contraexemplo (P08);
- rodada única, variação não medida na configuração congelada (P09);
- teto de 42 por causa de `struct.error` (P04);
- seleção favorável ao ESBMC e agrupamento por projeto (P20; AP §5.1);
- um modelo só, hospedado, sem semente, com contexto do CLI não registrado (P13, P14);
- rotulador único e risco de contaminação não quantificado (P17, P19);
- baselines em unidades diferentes (P10).

### 2.10 É realmente necessário um experimento novo antes da entrega?

**Não** [I]. Motivos:
1. A disciplina não exige conjunto independente; o próprio README e a `REGRA_DE_ACERTO` já tratam os 47 como desenvolvimento, e o artigo pode rotular os resultados assim.
2. As três RQs recomendadas se respondem com os JSON de 16/11 e das rodadas anteriores. As análises que faltam (sensibilidade, funil, taxonomia) são **reanálise sem LLM**, já feitas em boa parte nas auditorias e conferidas aqui.
3. Os experimentos pagos possíveis não mudam o que o artigo pode afirmar: a detecção nas corrigidas sem verificação não mede falso positivo (uma hipótese numa função corrigida não é alarme falso sem o ESBMC e o replay); a r2 mede só a variação da verificação e custa de US$ 37,61 a 136,80, além de cota e de 4 h de relógio; e qualquer resultado novo precisaria de tempo de escrita que não existe com folga.
4. O tempo disponível (cerca de 42 h) é o recurso mais escasso. Um experimento novo compete com a escrita e com a verificação das referências, que são obrigatórias.

---

## 3. Checklist de entrega CPS

**Decisões (suas)**
- [ ] Título, RQs e escopo escolhidos e anotados (seção 2).
- [ ] Denominador principal decidido (47 ou 42) e o outro mostrado ao lado.
- [ ] Variantes de sensibilidade fixadas antes de escrever Resultados.
- [ ] Scans: entram como parágrafo curto ou ficam fora.
- [ ] Mudança em relação à proposta de 22/09 declarada (P22).

**Números**
- [ ] Todo número do texto tem linha em `mapa_dados.md` com a pasta e o campo.
- [ ] "8" sempre é o `by_function.confirmado_esbmc`.
- [ ] Rodadas citadas pelo nome da pasta, não só pela data.
- [ ] Nenhuma precisão, recall, `fp` ou F1.
- [ ] Nenhuma soma de rodadas apresentada como medida.

**Documentos do repositório**
- [ ] `mapa_dados.md` e `tabela_experimentos.md` sem "em andamento" para 16/11 e sem "fora da amostra" para 06/11.
- [ ] Comentários do `artigo.tex` corrigidos (21 projetos; regra por função).
- [ ] Citação a `RECUSAS_ESBMC.md` resolvida (criar ou tirar).
- [ ] Rodada de 16/11 preservada de forma que sobreviva ao `.gitignore` (decisão sua).
- [ ] `agente-teste-2026-11-16` registrada como piloto ou como descartada (decisão sua).

**Referências**
- [ ] Cada referência conferida em DBLP ou Crossref (título, autores, local, ano, DOI) e lida por você pelo menos no resumo.
- [ ] Link de cada referência anotado (exigência do protocolo do guia).
- [ ] Nenhuma referência por memória, nem minha nem sua.

**Uso de IA (diretrizes, `SKILL.md`)**
- [ ] Seção "Declaração de uso de IA" escrita por você, com o uso real: Claude Code e Codex no código do pipeline, nas auditorias, nas contagens e na organização dos dados; revisão de texto, se houver. Não escrever "apenas gramática" se houve análise ou reescrita.
- [ ] Laudos de duas ou mais ferramentas de detecção, como pede o protocolo do guia (`diretrizes-integral.txt:163`). Registrar como exigência do guia; não editar texto para "passar" no detector; não enviar o manuscrito a serviço externo sem você decidir.
- [ ] Revisão humana declarada só se houve de fato.

**Formato**
- [ ] Compila em IEEEtran (Overleaf ou local), sem avisos de referência indefinida.
- [ ] Limite de páginas e formato da disciplina conferidos com o professor [NV: não achei no repositório].
- [ ] Nenhum travessão; figuras legíveis em preto e branco.
- [ ] PDF final e fontes (`.tex`, `.bib`, figuras) guardados com data.

---

## 4. Cronograma diário de 17/11 a 30/11

Ordem pedida: metodologia e arquitetura primeiro. As horas são estimativas; "CC" quer dizer "com apoio do Claude Code, revisão sua".

| Data | Horas | Objetivo | Tarefas | Depende de | Entregável | Pronto quando |
|---|---:|---|---|---|---|---|
| ter 17/11 | 2 | Decidir o escopo | ler as seções 1 e 2 deste documento; escolher título, RQs, denominador e se os scans entram | nada | decisões anotadas no topo do `artigo.tex` como comentário | as quatro decisões estão escritas |
| qua 18/11 | 2 | Limpar a base | corrigir `mapa_dados.md`, `tabela_experimentos.md`, comentários do `artigo.tex`; resolver a citação do `RECUSAS_ESBMC.md`; decidir como guardar a rodada de 16/11 (CC) | 17/11 | arquivos corrigidos | `grep "em andamento"` e `grep "20 projetos"` não acham mais nada nos arquivos do artigo |
| qui 19/11 | 2 | Método: conjunto de dados | escrever a subseção; montar T1 (projetos, tipos de exceção, funções) | 18/11 | subseção e T1 | cada número de T1 bate com o manifesto |
| sex 20/11 | 2 | Método: pipeline | escrever a subseção com a tabela 2.4 como guia; desenhar F1 (pode ser TikZ, draw.io ou à mão digitalizada) | 19/11 | subseção e F1 | F1 mostra quem é LLM e quem é código, e compila |
| sáb 21/11 | 5,5 | Método: critério de acerto e métricas; preparar números | escrever a subseção (regra por função, dois níveis, teto de 42, variantes de sensibilidade fixadas); CC: script só de leitura que regera T2, T3 e T4 a partir dos JSON (você decide se entra em `scripts/` e se é commitado) | 20/11 | subseção; T2, T3, T4 com números | o script reproduz 13, 11, 8, 4 e o funil 8/5/5/5/20/3/1 |
| dom 22/11 | 5,5 | Resultados | escrever RQ1, RQ2, RQ3; T5 (baselines por unidade); conferir cada número no `mapa_dados.md` | 21/11 | seção Resultados | não há número sem fonte |
| seg 23/11 | 2 | Referências mínimas | listar as referências necessárias (seção 5.1); conferir cada uma com o agente `citation-verifier` ou a skill `citation-verification`; criar `referencias.bib` | nada (pode adiantar) | `.bib` só com VERIFIED | toda entrada tem DOI ou arXiv e link |
| ter 24/11 | 2 | Fundamentação e trabalhos relacionados | ler os resumos das referências conferidas; escrever a seção | 23/11 | seção | só cita o que está no `.bib` conferido |
| qua 25/11 | 2 | Ameaças e discussão | escrever Ameaças (lista 2.9) e Discussão (o que uma confirmação significa; limites do ESBMC-Python); decidir se RQ4 entra | 22/11 | duas seções | cada limitação de 2.9 aparece |
| qui 26/11 | 2 | Introdução e conclusão | completar a introdução que você já começou (contribuições e RQs alinhadas aos resultados); escrever a conclusão sem afirmar além de 2.7 | 22 e 25/11 | duas seções | a conclusão só usa frases sustentadas |
| sex 27/11 | 2 | Resumo e declaração de IA | resumo; título final; declaração de uso de IA | 26/11 | resumo e declaração | a declaração descreve o uso real |
| sáb 28/11 | 5,5 | Revisão completa | ler tudo do começo; conferir números contra `mapa_dados.md`; `grep` de travessão; compilar; legendas; laudos do protocolo | 27/11 | versão revisada | checklist da seção 3 quase todo marcado |
| dom 29/11 | 5,5 | **Reserva** | imprevistos; ajustes da revisão; leitura em voz alta; se você quiser, enviar ao Lucas (decisão sua) | 28/11 | versão quase final | nada pendente além de detalhes |
| seg 30/11 | 2 | Fechar | PDF final; guardar fontes com data; última passada no checklist | 29/11 | PDF | checklist inteiro marcado |

**Reservas embutidas:** o domingo 29/11 inteiro (5,5 h) e parte de 28/11. Referências têm dia próprio (23/11) e podem ser adiantadas em qualquer brecha. LaTeX entra no dia 20/11 (figura) e no 28/11 (compilação final).

**Plano de contingência.**
- **Atraso de um dia até 22/11:** cortar RQ4 e o parágrafo dos scans; usar o domingo 29/11.
- **Atraso de dois dias ou mais:** cortar também T5 (baselines vira uma frase) e a figura do funil (fica só a tabela T3).
- **Referência que não verifica:** sai do texto. Melhor menos referências conferidas do que uma errada.
- **Script de tabelas com problema:** usar os números já conferidos nas auditorias (A4 §11, A5 §5.1, `RELATORIO_BUGS.md`), citando a fonte.
- **LaTeX quebrando:** passar para o Overleaf, que já tem a classe IEEEtran.
- **Disco E: indisponível:** não afeta, porque nenhuma etapa do plano roda o ESBMC; os JSON estão em `artifacts/`, no disco do WSL.
- **Versão mínima entregável** (se tudo der errado): Introdução, Método, Resultados (T2 e T3), Ameaças, Conclusão, declaração de IA e referências conferidas.

---

## 5. Estrutura do artigo em LaTeX

### 5.1 Plano por seção (Etapa 3)

| Seção | Subseções | Objetivo | Evidência (caminho) | Referências necessárias [todas NV até conferir] | Figuras e tabelas | Pendências | Pronto quando |
|---|---|---|---|---|---|---|---|
| Introdução | (texto corrido; contribuições) | motivar e dizer o que o trabalho faz | seu texto atual no `artigo.tex`; seção 2.2 | fonte do índice TIOBE que você citou; ESBMC-Python; 1 ou 2 sobre LLM para bugs | | ligar o último parágrafo às RQs | RQs e contribuições batem com Resultados |
| Fundamentação e trabalhos relacionados | BMC e ESBMC-Python; LLM para detecção; LLM + verificação formal; geração de harness | situar o trabalho | `trabalhos_relacionados_2026-10-16.md`; A6 §3 | Biere et al. (BMC); ESBMC; Farias et al. (ESBMC-Python); BugsInPy; mypy (documentação); Shivaji et al. e Orvalho e Kwiatkowska (os mais próximos); 1 de harness (ex.: HarnessLLM) | | conferir os metadados divergentes (P24) | só referências VERIFIED |
| Método: conjunto de dados | origem, critérios, rótulos | dizer de onde vêm os 47 e o viés | `manifest.json`; `ORIGEM_DOS_47_BUGS.md`; AP §5.1; A2 §2 | | T1 | declarar bônus de seleção e rotulador único | T1 confere com o manifesto |
| Método: pipeline | detecção, especificação, ESBMC, healing, replay, veredito | descrever o que o código faz | tabela 2.4; AP §3; A4 §1 e §6 | ESBMC-Python | F1 | | F1 e texto não contradizem o código |
| Método: critério de acerto e métricas | regra por função; níveis; teto; sensibilidade | definir antes de mostrar | `REGRA_DE_ACERTO_2026-11-14.md`; A2 §4.1; A4 §11 | (Wilson, se citar o método do intervalo) | | variantes fixadas | as variantes estão escritas antes da tabela |
| Método: protocolo da rodada | pré-registro, perfil congelado, procedência | mostrar o controle que existe | `docs/experimentos/README.md` (rodada de 16/11); `commit.txt`; AP §1 item 1 | | | | horários do commit e da rodada citados |
| Método: linhas de comparação | mypy; testes do PR | dizer cada unidade | A5 §9 | mypy | | | unidades explicadas |
| Resultados | RQ1; RQ2; RQ3; (RQ4) | responder às RQs | seção 2.7; `RELATORIO_BUGS.md`; A4 §12 | | T2, T3, T4, T5, (T6) | | cada número com fonte |
| Discussão | o que uma confirmação significa; o gargalo do ESBMC-Python; baselines | interpretar com cuidado (texto seu) | A4 §9 e §13; A2 §5 | | | | não há afirmação fora de 2.7 |
| Ameaças à validade | interna, construto, externa, conclusão | listar limitações | lista 2.9; AP §9 | (contaminação, se citar) | | | os dez itens de 2.9 aparecem |
| Conclusão | | fechar | Resultados | | | | sem novidade não sustentada |
| Declaração de uso de IA | | exigência do guia | `SKILL.md`; `diretrizes-integral.txt:156-168` | | | laudos | uso real descrito |

### 5.2 Esqueleto (só estrutura e comentários; o texto é seu)

Manter o cabeçalho atual do `artigo.tex` (classe `IEEEtran`, pacotes, autoria). O esqueleto abaixo substitui só os comentários, e **mantém os quatro parágrafos da Introdução que você já escreveu** (diff não commitado de 16/11).

```latex
\title{TÍTULO A DEFINIR}  % opções na seção 2.1 do plano de consolidação

\begin{abstract}
% O que vai aqui: problema, abordagem, dados (47 bugs, 21 projetos, conjunto de
% desenvolvimento), resultado principal (13/47 e 8/47 na rodada pré-registrada),
% limite principal (confirmação no harness).
% Evidência: seção 2.7 do plano; AP §6.1.
\end{abstract}

\begin{IEEEkeywords}
% ESBMC, Python, verificação limitada de modelos, sistemas ciberfísicos, modelos de linguagem
\end{IEEEkeywords}

\section{Introdução}
% [Manter os 4 parágrafos já escritos pela autora.]
% O que falta aqui: o que este trabalho faz, as RQs escolhidas e as contribuições
% em lista curta, sem prometer localização nem precisão.
% Referência pendente: fonte do índice TIOBE (conferir e pôr o link).

\section{Fundamentação e Trabalhos Relacionados}
\subsection{Verificação limitada de modelos e ESBMC-Python}
% Evidência: trabalhos_relacionados_2026-10-16.md, itens 2 e 7. Só citar o que estiver
% VERIFIED no .bib (ver P24: DOI do ESBMC-Python divergente entre TR e fichamento).
\subsection{LLMs na detecção de defeitos}
% Evidência: A6 §3.1, eixo "LLMs para detecção". Escolher 1 ou 2 lidos por você.
\subsection{LLMs combinadas com verificação formal e geração de harness}
% Evidência: TR itens 3, 4 e 9. Diferença em relação a eles: escrita por você e
% sem dizer "confirmação no código original" (não sustentada, A6 §1.4).

\section{Método}
\subsection{Conjunto de dados}
% O que vai aqui: origem dos 47 (PRs integrados, duas rodadas de mineração),
% 21 projetos, 53 funções, tipos de exceção esperada, versão com bug e corrigida.
% Declarar: critérios davam bônus ao que o ESBMC suporta; rotulador único; 13 rótulos
% vizinhos do guarda; conjunto de desenvolvimento.
% Evidência: dataset/disciplina_pgene601/manifest.json; docs/projeto/ORIGEM_DOS_47_BUGS.md;
% AP §5.1; A2 §2.5. Tabela T1.
\subsection{Pipeline}
% O que vai aqui: os 11 passos da tabela 2.4 do plano, separando LLM e código.
% Evidência: AP §3; A4 §1, §3, §6, §7. Figura F1.
\subsection{Critério de acerto e métricas}
% O que vai aqui: regra por função em dois níveis (REGRA_DE_ACERTO_2026-11-14.md);
% "apontado" não discrimina; teto de 42 (struct.error, A2 §4.1); variantes de
% sensibilidade fixadas antes dos resultados (A4 §11); intervalo de Wilson.
\subsection{Protocolo da rodada}
% O que vai aqui: pré-registro (commit f086e22 às 13:11:11, rodada às 13:11:17),
% perfil congelado, ESBMC de72a905e0 com sha256, modelo e backend, custo.
% Evidência: docs/experimentos/README.md (rodada de 16/11); commit.txt; AP §1 item 1.
\subsection{Linhas de comparação}
% O que vai aqui: mypy (padrão e --check-untyped-defs) e testes dos PRs, cada um
% na sua unidade. Evidência: A5 §9.1 e §9.2. Tabela T5.

\section{Resultados}
\subsection{RQ1: evidência produzida por nível}
% Evidência: congelado-2026-11-16-r1/v2_verify_report.json (evaluation.by_function);
% AP §6.1. Tabela T2 (parte oficial).
\subsection{RQ2: significado e robustez das confirmações}
% Evidência: A4 §9 e §11; A2 §3.2 e §8; A5 achado 4. Tabela T2 (sensibilidade).
% Casos para exemplo: simpleio_43 (inequívoco), pymodbus_2921 (assinatura trocada),
% blinka_434 (guarda injetada), mavproxy_881 (estado irreal, fora dos 8).
\subsection{RQ3: onde as hipóteses param}
% Evidência: RELATORIO_BUGS.md (funil, com a regra de precedência explicada);
% A4 §12 (taxonomia) e §13 (limites com mensagem real). Tabelas T3 e T4.
% \subsection{RQ4: variação entre rodadas (exploratória)}
% % Só se couber. Evidência: A5 §5.1 e §3.2. Tabela T6. Nunca chamar de réplicas.

\section{Discussão}
% O que vai aqui (interpretação sua): o que uma confirmação no harness permite e
% não permite dizer; por que o frontend Python é o gargalo; o que mypy e testes
% pegam em comparação, sem pôr tudo na mesma linha.
% Evidência: A4 §15; A2 §8; A5 §9.2. Scans (opcional): A3 §9.

\section{Ameaças à Validade}
% O que vai aqui: os dez itens da lista 2.9 do plano, agrupados em interna,
% construto, externa e conclusão. Evidência: AP §9.

\section{Conclusão}
% O que vai aqui: só o que a seção 2.7 sustenta; trabalhos futuros (conjunto
% independente, negativos, repetições) sem prometer datas.

\section*{Declaração de uso de IA}
% Escrita pela autora. Uso real: ferramentas (Claude Code, Codex), finalidades
% (código do pipeline, auditorias, contagens, organização de dados, revisão de texto
% se houver). Conforme docs/escrita/revisar-escrita-academica/SKILL.md.

\bibliographystyle{IEEEtran}
\bibliography{referencias}  % só entradas VERIFIED
```

---

## 6. Tabelas e figuras

| ID | Conteúdo | Fonte dos dados | Como gerar | Custo | Indispensável? |
|---|---|---|---|---|---|
| F1 | Arquitetura: passos, quem decide (LLM ou código), onde entram healing e refinamento | tabela 2.4; A0 §2 (fluxograma em texto) | desenhar à mão ou em TikZ/draw.io | 0 | sim |
| T1 | Dataset: projetos (21), bugs por projeto, tipos de exceção (TypeError 10, IndexError 7, AttributeError 7, ValueError 6, struct.error 5, UnboundLocalError 4, KeyError 4, ZeroDivisionError 3, UnicodeDecodeError 1), funções (53) | `manifest.json`; A2 §2.3 | leitura do manifesto (CC) | 0 | sim |
| T2 | Resultado por nível: oficial, estrito, teto 42, variantes de sensibilidade, núcleos | A4 §11; A5 §5.1; seção 2.7 | script de leitura (CC) ou cópia dos números das auditorias | 0 | sim |
| T3 | Funil por bug, com a regra de precedência escrita na legenda | `RELATORIO_BUGS.md`; AP §5.2 | já existe; conferir a ordem dos estágios | 0 | sim |
| T4 | Taxonomia das 65 hipóteses sem veredito (categoria do relatório e reclassificação), com exemplos de mensagem | A4 §12 e §13 | cópia da A4, revisada por você | 0 | sim |
| T5 | Baselines por unidade (mypy, testes do PR, LLM na expressão, pipeline), com células vazias onde não existe medida | A5 §9.1 e §9.2 | cópia da A5 | 0 | sim, ou vira frase na contingência |
| T6 | Confirmados por rodada (seis rodadas), marcadas como configurações diferentes | A5 §5.1; seção 1.3 item 2 | cópia | 0 | não (só com RQ4) |
| F2 | Funil em barras | T3 | matplotlib (CC) | 0 | não |
| T7 | Scans CPS (GPS, pynmea2, pyserial): funções, hipóteses, CONFIRMED, triagem | A3 §6.1 e §7 | cópia | 0 | não |

---

## 7. Experimentos novos realmente indispensáveis

**Nenhum** (justificativa em 2.10).

O que é indispensável é **reanálise sem LLM**, sobre dados que já existem:

| Reanálise | Para quê | Estado | Como |
|---|---|---|---|
| Tabela de sensibilidade de 16/11 | T2, RQ2 | calculada na A4 §11 e na A5; exclusões (b) e (d) conferidas aqui | transformar em script de leitura reproduzível (CC, revisão sua) |
| Funil com precedência explicada | T3, RQ3 | `RELATORIO_BUGS.md` existe; script fora do git | decidir se commita o `scripts/relatorio_bugs.py` |
| Taxonomia das perdas | T4, RQ3 | A4 §12 (reclassificação é interpretação da IA) | você revisa as categorias |
| Tabela dos dois "8" e dos CONFIRMED com tipo diferente | evitar erro no texto | A2 §3.2 | cópia |

**Opcionais, sem LLM, que exigem rodar código** (só se você autorizar e sobrar tempo):
- **Juiz do conserto** (`scripts/juiz_conserto.py`): roda o replay no CPython com a função corrigida, sem LLM e sem ESBMC (docstring do script). Daria um controle com arquivo de resultado, no lugar do "4" sem fonte (A5 §9.1). Custo 0; precisa conferir o que ele grava.
- **Datas dos 47 PRs** pela API do GitHub (`gh api`), para a ameaça de contaminação (P19). Custo 0; usa rede.

**Pagos, não recomendados antes de 30/11** (cada um só com sua confirmação):
- detecção nas corrigidas: US$ 4,44 (base A) a 8,13 (base B), mas sem verificação não mede falso positivo;
- teste do contexto do CLI: US$ 0,08 a 0,15; útil para reprodutibilidade, não para o artigo;
- r2 só verificação: US$ 37,61 a 136,80 e cerca de 4 h.

---

## 8. Backlog do mestrado (Etapa 5) e priorização (Etapa 6)

Qualificação até fevereiro de 2027, com folga. Sugestão de calendário [I, a partir da A6 §7]: dezembro (depois da entrega) para RQs com o Lucas, revisão bibliográfica e regra de seleção pré-registrada; segunda quinzena de dezembro para mineração e rotulagem; até 20/01 para as rodadas; até 05/02 para análise e texto; o resto de fevereiro como folga. O texto da qualificação não deveria depender dos resultados do conjunto novo: se as rodadas atrasarem, ele entra como protocolo pré-registrado com piloto (A6 §7).

### 8.1 Backlog P0 a P3

| Pri. | Tarefa | Tema | Depende de | Pronto quando | Fonte |
|---|---|---|---|---|---|
| P0 | Escrever e commitar a regra de seleção do conjunto independente antes de qualquer consulta | dataset independente | RQs escolhidas | documento com data e commit anterior à primeira consulta; campos do modelo da A6 §5.5 preenchidos | AP §12 item 1; A6 §5 |
| P0 | Resolver o contexto injetado pelo CLI (testar com 1 chamada; bloquear ou trocar para API com parâmetros gravados) | reprodutibilidade | sua autorização (US$ 0,08) | entrada do modelo documentada e igual em qualquer máquina | AP achado 10; A5 achado 7 |
| P0 | Escolher as RQs da dissertação com o Lucas | qualificação | entrega de CPS | RQs escritas, com métrica principal única | A6 §4 e §9 |
| P0 | Revisão bibliográfica estruturada, com citações conferidas | trabalhos relacionados | nada | busca registrada (bases, termos, data); tudo VERIFIED | A6 §3.2 |
| P1 | Controles negativos: versões corrigidas e funções sem defeito conhecido do mesmo arquivo | controles negativos | regra P0; script de verificação nas corrigidas [NV se roda] | taxa de alarme por condição, com Wilson | A6 §6.3; A5 §12 |
| P1 | Baselines na mesma unidade e com a mesma entrada: LLM sozinha, pipeline sem ESBMC, mypy e pyright pela regra por função, fuzzing simples | baselines | modo sem ESBMC no código [NV] | tabela braço por braço na mesma unidade | A5 §9.3; A6 §6.2 |
| P1 | Pelo menos 3 repetições por configuração, separando variação da detecção e da verificação | repetições | P0 do contexto; cota | variação por bug com intervalo; kappa de Fleiss | AP §6.3; A6 RQ4 |
| P1 | Preservação semântica: gravar assinatura nas duas cópias, origem da entrada do replay, linha e função da violação do ESBMC; separar `Unsupported:` e erros internos | preservação semântica | nova versão congelada | os campos aparecem no relatório e a sensibilidade sai automática | A4 §16 itens 1 a 5 |
| P1 | Corrigir o teto de `struct.error` (nome qualificado no replay; stub de `struct.unpack` que levanta) | métricas | nova versão congelada | um bug de `struct.error` pode ser reproduzido em teste | A2 §7 item 2 |
| P1 | Métrica principal estrita pré-registrada (hipótese no rótulo, linha do replay no rótulo, tipo esperado) e a atual como secundária | métricas | P0 | definida antes das rodadas | A2 §6 item 2; A6 §8 |
| P1 | Análise estatística: McNemar exato ou modelo misto com bug e projeto; bootstrap por projeto; correção para múltiplas comparações | estatística | repetições | plano de análise escrito antes | AP §6.3 |
| P1 | Segundo rotulador numa amostra, com kappa; rodar a versão com bug para confirmar `expected_type` | grounding e gabarito | regra P0 | kappa calculado | A2 §7 item 6 |
| P1 | Anotação das confirmações (fiel ao defeito, sem mudança de semântica, alcançável) com dois anotadores | grounding e gabarito | confirmações do conjunto novo | proporções e kappa | A6 RQ3 |
| P2 | Reprodutibilidade: arquivar binário do ESBMC com sha256 fora do build; gravar `git status`, versão do CLI e prompt completo por chamada; tirar a rodada de 16/11 da dependência do `.gitignore` | reprodutibilidade | nada | checklist da AP §8 todo "atendido" | AP §8; A5 §7.1 |
| P2 | Corrigir o comparador de expressões (`;` e cabeçalhos `for`/`if`) | métricas | nada | recálculo das rodadas antigas | A2 §6 item 3 |
| P2 | Datas dos PRs e sonda de memorização | contaminação | rede | `merged_at` no manifesto | AP §12 item 9; A6 §5.2 |
| P2 | Orçamento: estimar custo de cada rodada antes (base A e B) e espalhar pela cota da assinatura | custo | nada | estimativa registrada antes de cada rodada | A5 §12 (N = 50 e 3 rodadas: US$ 134 a 463, acima do crédito de US$ 100) |
| P2 | Scan: triar os 22 CONFIRMED pendentes com regra escrita antes; registrar as rodadas de 13 e 14/11 no README; gravar commit do pipeline e do alvo no `scan_report.json` | scan | nada | falso positivo medido na amostra triada | A3 §10 e §11 |
| P2 | Atualizar `entendendo_o_pipeline.md` e `CONGELAMENTO_2026-11-14.md` | documentação | nada | sem as divergências da A0 §10 | AP §12 item 12 |
| P3 | Ablação do healing e do refinamento | ablação | repetições | efeito com intervalo | AP §12 item 18 |
| P3 | Prova de alcance pelo chamador real (L4/L5) | alcance | nada | caminho real demonstrado numa amostra | A3 §10; A2 §7 item 4 |
| P3 | Segundo modelo na configuração congelada | generalização | orçamento | comparação pareada | A6 §6.6 |
| P3 | Ampliar domínio de `bytes` e inteiros no harness e no replay | harness | nova versão | número de bugs que entram | A2 §4.6 |
| P3 | Publicação: artigo com as RQs respondidas no conjunto independente | publicação | todos os P1 | submissão | A6 §7 |

### 8.2 Priorização por tarefa (Etapa 6)

Colunas: **<30/11** antes de 30/11? **CPS** indispensável para CPS? **Mest.** indispensável para o mestrado? **Espera** pode esperar? **LLM / Cód. / Exp.** requer LLM, código, experimento? **Resultado** o que rende academicamente.

| Tarefa | <30/11 | CPS | Mest. | Espera | LLM | Cód. | Exp. | Resultado |
|---|---|---|---|---|---|---|---|---|
| Decidir título, RQs, escopo | sim | sim | não | não | não | não | não | artigo coerente |
| Corrigir docs inconsistentes | sim | sim | sim | não | não | não | não | números sem erro |
| Preservar a rodada de 16/11 fora do `.gitignore` | sim | sim | sim | não | não | não | não | reprodutibilidade |
| Script de leitura para T2, T3, T4 | sim | sim | sim | não | não | pequeno (CC) | não (reanálise) | tabelas reproduzíveis |
| Escrever Método, Resultados, Ameaças | sim | sim | não | não | não | não | não | o artigo |
| Verificar referências | sim | sim | sim | não | não | não | não | citações corretas |
| Declaração de IA e laudos | sim | sim | sim | não | não | não | não | conformidade com o guia |
| Juiz do conserto | opcional | não | sim | sim | não | roda script | sim (sem LLM) | controle com arquivo |
| Datas dos PRs | opcional | não | sim | sim | não | pequeno | não | ameaça de contaminação medida |
| Detecção nas corrigidas | não | não | sim | sim | sim | não | sim | piloto de negativos |
| r2 e r3 | não | não | sim | sim | sim | não | sim | variação da verificação |
| Teste de contexto do CLI | não | não | sim | sim | 1 chamada | não | sim | reprodutibilidade |
| Regra do conjunto independente | não | não | sim | até dezembro | não | não | não | validade externa |
| Negativos e baselines na mesma unidade | não | não | sim | até janeiro | sim | sim | sim | precisão e valor do ESBMC |
| Preservação semântica no código | não | não | sim | sim | não | sim | nova rodada | construto mais limpo |
| Segundo rotulador e anotação | não | não | sim | sim | não | não | não | kappa |
| Triagem dos 22 do scan | não | não | não | sim | não | não | não | falso positivo no scan |
| Ablações, alcance real, outro modelo | não | não | não (desejável) | sim | sim | sim | sim | artigo de pesquisa |

---

## 9. Riscos e contingência

| Risco | Probabilidade [I] | Efeito | Mitigação | Contingência |
|---|---|---|---|---|
| Tempo menor que o previsto (trabalho, cansaço) | alta | seções incompletas | cronograma com reserva; um item por dia | versão mínima da seção 4 |
| Tentação de rodar "só mais uma" rodada | média | perde dias e cota; número novo sem tempo de texto | regra desta seção e da seção final | anotar a ideia em "Depois" |
| Número errado no texto (os dois "8", rodada pela data) | média | perda de credibilidade | `mapa_dados.md` como fonte única; checklist | revisão de números em 28/11 |
| Referência errada ou inventada | média | problema de integridade | só VERIFIED no `.bib`; ler o resumo | tirar a referência |
| Afirmação além da evidência | média | rejeição | lista "não defensáveis" de 2.7 | revisão final contra 2.7 |
| Perder os artefatos de 16/11 (`.gitignore`, disco) | baixa | resultado sem fonte | preservar em 18/11 | os resumos nas auditorias |
| Professor esperar a pergunta da proposta | baixa a média [NV] | desalinhamento | declarar a mudança (P22) | conversa breve com o professor, se você decidir |
| LaTeX ou Overleaf falhar perto da entrega | baixa | atraso | compilar cedo (20/11) | Overleaf ou PDF local |
| Laudos de IA acima do limite | [NV] | exigência do guia | escrever com suas palavras; declarar o uso real | não reescrever para burlar; conversar com o orientador |

---

## 10. Próximas cinco ações, em ordem

1. **Decidir título, RQs, denominador (47 ou 42) e se os scans entram** (17/11, 2 h). Base: seção 2.
2. **Corrigir os documentos do artigo** (18/11): `mapa_dados.md`, `tabela_experimentos.md`, comentários do `artigo.tex`, citação do `RECUSAS_ESBMC.md`. Critério: os `grep` da seção 4 voltam vazios.
3. **Preservar a rodada de 16/11** e decidir o destino da `agente-teste-2026-11-16` (18/11, junto com a ação 2). Base: seção 1.3 itens 13 e P23.
4. **Escrever "Método: conjunto de dados" com T1** (19/11).
5. **Escrever "Método: pipeline" com F1** (20/11), usando a tabela 2.4 para não repetir as divergências entre documentação e código.

---

## O que NÃO devo fazer antes de 30/11

- Rodar qualquer rodada nova com LLM (r2, corrigidas, conjunto novo), mesmo pela assinatura.
- Mudar o pipeline congelado, inclusive o `healing.py` não commitado, ou "consertar" o avaliador para melhorar o número.
- Escolher as variantes de sensibilidade depois de ver qual dá o número mais bonito.
- Chamar os 47 de "fora da amostra", ou a rodada de 06/11 de "única fora da amostra".
- Citar precisão, recall, F1 ou o `fp` dos relatórios.
- Dizer que o pipeline localiza bugs, prova o bug no código real ou usa a mesma entrada no ESBMC e no CPython.
- Somar rodadas ou apresentar a união como resultado.
- Comparar o 8/47 com números de outubro ou do BugsInPy como evolução.
- Pôr mypy, testes e pipeline numa linha só como se medissem a mesma coisa.
- Citar referência que não foi conferida em DBLP ou Crossref e lida por você.
- Minerar bugs novos ou escrever a regra do conjunto independente às pressas.
- Triar os 22 CONFIRMED da Amazon ou abrir issues novas no ESBMC.
- Recompilar o ESBMC no caminho do binário de 16/11 sem antes guardar uma cópia.
- Começar frentes novas: ideias que surgirem vão para "Depois".

---

## Declaração de uso de IA neste documento

Este plano foi produzido pelo Claude Code (Opus 5.5) a pedido da Fernanda, a partir da leitura das auditorias e de conferências por script de leitura. A síntese dos problemas, as propostas de título, RQs, escopo, cronograma e priorização, e a reconciliação das contradições são interpretação e organização da IA. Não são decisões da autora e precisam da revisão dela. Nenhuma referência bibliográfica foi conferida nesta sessão. Não houve revisão humana antes desta entrega.
