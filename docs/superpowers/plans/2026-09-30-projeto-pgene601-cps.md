# Projeto PGENE601: verificação guiada por LLM de software Python ciber-físico

Versão de trabalho (com caminhos e comandos). A versão para o professor sai deste plano, em tom
acadêmico e sem caminhos.

**Pergunta:** o pipeline LLM + ESBMC-Python, validado em Python de propósito geral (dataset V2),
mantém a detecção e a confirmação formal em software Python que controla ou conversa com sistemas
ciber-físicos e embarcados? E o que ele encontra que mypy e pytest não encontram?

**Ideia central (a contribuição para a disciplina):** nesse software, o hardware aparece como
biblioteca (`machine.Pin`, `board.I2C`, `serial.Serial`, `can.Bus`, `rclpy`). O pipeline já troca
toda biblioteca desconhecida por um substituto com valor não determinístico; no contexto
ciber-físico isso significa que a leitura de sensor, o quadro de rede ou o registrador podem ter
qualquer valor, que é como se verifica software embarcado.

**Arquitetura:** o pipeline não muda. O trabalho novo é um dataset separado, um script de
comparação com mypy e pytest, e a análise.

## Restrições

- Dataset da disciplina separado do da dissertação: `dataset/cps_pgene601/`, mesmo formato de
  `dataset/v2_real_world/` (para rodar sem mudar o pipeline). Não mistura com os 116 nem com os 199
  candidatos.
- Mesma exigência de proveniência da dissertação: só bugs cuja correção foi aceita pelo mantenedor
  (PR com merge ou commit de correção no repositório oficial).
- Pipeline congelado: mudança de código só se um caso real mostrar limitação, com teste.
- Documentos para o professor: tom acadêmico, sem travessão, sem caminho de arquivo ou comando.
- Sem commit ou push sem pedido explícito. Rodadas pagas só com aprovação.
- Artigo no template IEEE; apresentação final de 20 minutos; semanais de 5 a 10 minutos, até 5
  slides.

## Artigos da lista do professor que casam com o projeto

Conferidos em fonte oficial em 30/09/2026 (Crossref, arXiv, CEUR-WS, resumo pelo Semantic Scholar): título, autores, local e ano.

| # | Referência | Papel no projeto |
|---|---|---|
| 15 | B. Farias, R. Menezes, E. B. de Lima Filho, Y. Sun, L. C. Cordeiro. "ESBMC-Python: A Bounded Model Checker for Python Programs". ISSTA 2024, pp. 1836-1840. DOI 10.1145/3650212.3685304 | **tópico principal**; o entregável sugerido (verificar módulo Python real e comparar com mypy e pytest) vira o experimento E2 |
| 33 | W. Wang, M. Farrell, L. C. Cordeiro, L. Zhao. "Supporting Software Formal Verification with Large Language Models: An Experimental Study". RE 2025, pp. 423-431. DOI 10.1109/RE63999.2025.00049 | SpecVerify: LLM (Claude 3.5) + ESBMC geram propriedades a partir de requisitos em linguagem natural, em nove sistemas ciber-físicos da Lockheed Martin (46,5% de acurácia); compara Claude, ChatGPT e Llama. Base de E1b, E1c e E4 |
| 32 | N. Tihanyi, Y. Charalambous, R. Jain, M. A. Ferrag, L. C. Cordeiro. "A New Era in Software Security: Towards Self-Healing Software via Large Language Models and Formal Verification". AST 2025, pp. 136-147. DOI 10.1109/AST66626.2025.00020 | BMC acha a vulnerabilidade, a LLM corrige com contraexemplo e pilha, BMC reverifica (ferramenta ESBMC-AI). Base do E5 |
| 34 | Y. Charalambous, C. N. Coelho Jr., L. C. Lamb, L. C. Cordeiro. "UnitTenX: Generating Tests for Legacy Packages with AI Agents Powered by Formal Verification". GeCoIn@ECAI 2025, CEUR-WS vol. 4075 | agente de IA guiado por verificação formal; paralelo ao braço com agente |
| 1 | P. Dantas, L. Cordeiro, W. Junior. "ESBMC: A Survey of Its Evolution, Integration, and Future Directions in Formal Software Verification". arXiv 2605.26169, 2026 | contexto do ESBMC: nasceu para software embarcado e hoje se acopla a LLMs |
| 46 | L. C. Cordeiro, E. B. de Lima Filho, I. V. Bessa. "Survey on automated symbolic verification and its application for synthesising cyber-physical systems". IET Cyber-Physical Systems: Theory & Applications, vol. 5, no. 1, 2020. DOI 10.1049/iet-cps.2018.5006 | enquadramento ciber-físico da verificação simbólica |
| 52 | M. Luckcuck, M. Farrell, L. A. Dennis, C. Dixon, M. Fisher. "Formal Specification and Verification of Autonomous Robotic Systems: A Survey". ACM Computing Surveys, vol. 52, no. 5, 2019. DOI 10.1145/3342355 | enquadramento para os casos de robótica (ROS 2, drones) |
| 31 | M. A. A. Pirzada, J. Parsert, W. Wang, K. Korovin, L. C. Cordeiro. "Neuro-Symbolic Software Verification: Hyper-charging Local Language Models with Symbolic Reasoning at Scale". arXiv 2606.16886, 2026 | só trabalho relacionado (trata de invariantes de laço, não de detecção de bugs) |

Já verificados antes e usados no método (continuam valendo): Beyer et al. TAP 2018 (validação por
execução), Olausson et al. ICLR 2024 (reparo contra amostragem), Widyasari et al. ESEC/FSE 2020
(BugsInPy).

## Critérios de avaliação e onde cada um é atendido

| Critério | Pontos | Onde |
|---|---|---|
| tópico ligado à disciplina | 0,5 | #15 + software ciber-físico |
| contexto, problema e objetivos | 1,5 | Dev 1 |
| métodos, técnicas e ferramentas | 3,0 | pipeline + ESBMC + mypy + pytest (Dev 2 a 4) |
| implementação, experimentos, discussão | 4,0 | E1, E1b, E1c, E2, E3 e controle (Dev 3 a 5); E4 e E5 se houver tempo |
| trabalhos relacionados e desafios em aberto | 1,0 | tabela acima + limites do ESBMC-Python |

## Corpus: repositórios candidatos

Critérios: Python puro ou majoritário, domínio ciber-físico ou embarcado, histórico público de
correções de bug aceitas, testes pytest (para o E2).

| Repositório | Domínio |
|---|---|
| pymodbus | protocolo industrial Modbus (PLC, automação) |
| python-can, cantools | barramento CAN (automotivo, embarcado) |
| pyserial | comunicação serial com microcontroladores |
| pymavlink, MAVProxy, dronekit-python | drones (protocolo MAVLink) |
| micropython-lib, bibliotecas CircuitPython da Adafruit | drivers de sensor para microcontrolador |
| rclpy, launch, ros2cli (ROS 2) | robótica |

Meta: 15 a 20 bugs, cada um com arquivo com bug, arquivo corrigido, teste que falha antes da
correção e origem (URL do PR ou commit).

## Experimentos

- **E1, detecção e confirmação:** RQ1 (a LLM acha função e expressão), RQ2 (localização dada) e RQ3
  (ponta a ponta) no corpus ciber-físico, com gpt-4o-mini; comparação com os números do V2.
- **E2, ESBMC contra mypy contra pytest:** para cada bug, qual ferramenta o aponta. pytest usa o
  teste do próprio PR (falha antes, passa depois); mypy roda no arquivo com bug.
- **E3, substitutos de hardware:** quantas confirmações passam por substituto de biblioteca de
  hardware; discussão de quando o valor não determinístico é realista (sensor) e quando não é.
- **E1b, especificação aceita sem intervenção humana (entregável do artigo 33):** fração de hipóteses
  em que a especificação de entradas da LLM é aceita pelo validador e pelo ESBMC, com e sem reparo
  guiado. Sem código novo: sai de `verification.by_verdict` e `success_at_k`.
- **E1c, comparação de LLMs (como no artigo 33):** gpt-4o-mini, gpt-5.5 e um modelo local de peso
  aberto via backend Ollama (liga ao artigo 31). Custo aprovado caso a caso.
- **Controle:** versões corrigidas com `--verification-sources-strict`; toda confirmação ali é falsa.

### Opcionais (depois do Dev 3, se houver tempo; são os únicos que mudam o pipeline)

- **E4, docstring como requisito (ideia do artigo 33):** a LLM lê a docstring e devolve uma
  pós-condição no JSON (`"ensures": "result >= 0"`, mesma gramática restrita das pré-condições); o
  driver passa a checá-la com `assert`. Abre os bugs de resultado incorreto, que hoje não confirmam
  por não lançarem exceção. Risco: a LLM interpretar o requisito errado. Proteção: a pós-condição
  tem de valer na versão corrigida (controle), senão a especificação é descartada.
- **E5, reparo dos bugs confirmados (ideia do artigo 32, ferramenta ESBMC-AI):** para cada
  CONFIRMED, a LLM recebe contraexemplo e linha e propõe correção; medir se passa no ESBMC, se passa
  no teste do PR e se se parece com a correção do mantenedor ou só suprime o sintoma (ex.: `try`
  que engole a exceção). Antes: conferir se o ESBMC-AI aceita Python (a documentação não diz); se
  não aceitar, reproduzir o laço no próprio pipeline.

## Cronograma (datas da disciplina)

### Dev 1: 01/10 e 06/10: proposta
- [ ] Slides (até 5): contexto, pergunta, ideia do hardware como entrada não determinística, método,
  corpus candidato.
- [ ] Rascunho das seções Introdução e Trabalhos relacionados do artigo (tabela de artigos acima).

### Dev 2: 08/10 e 13/10: corpus
- [ ] Buscar PRs de correção de bug nos repositórios candidatos; lista para aprovação da Fernanda.
- [ ] Coletar os aprovados com `scripts/collect_validated_bugs.py prs <lista>` em
  `dataset/cps_pgene601/` (arquivo com bug, corrigido, teste, origem).
- [ ] Rotular função e expressão pela correção (`scripts/label_candidates.py`), revisão manual.
- [ ] Montar `manifest.json` e `ground_truths.json` no formato do V2; conferir que o pipeline aceita.

### Dev 3: 15/10 e 20/10: E1
- [ ] Rodar RQ2 e RQ3 com gpt-4o-mini (aprovação de custo) e o controle nas versões corrigidas.
- [ ] E1b (especificação aceita) e E1c (gpt-5.5 e modelo local).
- [ ] Tabela comparando com o V2.
- [ ] Decidir com a Fernanda se E4 e/ou E5 entram.

### Dev 4: 22/10 e 27/10: E2 e E3
- [ ] Script `scripts/cps_compare_tools.py`: roda mypy e o teste do PR em cada bug, junta com o
  veredito do pipeline.
- [ ] Contagem de confirmações que passam por substituto de hardware.

### Dev 5: 29/10 e 03/11: análise
- [ ] Limites do ESBMC-Python específicos do domínio (reprodutores mínimos).
- [ ] Resultados e discussão no artigo.

### Final: 05/11 a 08/12
- [ ] Artigo IEEE completo e apresentação de 20 minutos (entrega até 08/12, início de dezembro,
  conforme confirmado pela Fernanda em 30/09).

## Fora deste plano

A curadoria do dataset da dissertação (os 199 candidatos passando pelos portões de auditoria) é
outra frente e segue separada.
