# Harness de agente: o LLM só faz o código rodar no ESBMC (22/10/2026)

Documento de trabalho da Fernanda. Parte da reunião com o Lucas em 22/10 e continua o desenho de
self-healing de 19/10 ([`2026-10-19-self-healing-design.md`](2026-10-19-self-healing-design.md)), sem
substituí-lo: o que lá já existe (loop de reparo, `Healer`, conhecimento lido do checkout do ESBMC) é a base.

## Intenção

Na reunião, o Lucas disse três coisas que orientam este desenho:

- o pipeline faz contornos demais para o ESBMC rodar, e **mexer demais pode tirar o próprio bug**;
- o caminho é **agentes + stubs**, com o LLM servindo só para fazer o harness rodar;
- quando o ESBMC não aceita uma construção, **abrir issue** em vez de contornar.

A Fernanda resumiu o que o harness precisa garantir: **o comportamento do código no caminho do bug não muda.**
O harness pode acrescentar o que falta para rodar (driver, entradas `nondet_*`, stubs de biblioteca), mas não
pode inventar nem remover comportamento nesse caminho.

Ela também observou que o `/esbmc` (Claude Code com o plugin do ESBMC) funciona bem no uso interativo, mas o
pipeline não consegue fazer o código rodar no ESBMC. O objetivo prático é fechar essa distância: o pipeline
fazer sozinho o que o `/esbmc` faz quando ela usa na mão.

"Harness" aqui tem dois sentidos, e o desenho usa os dois:

- **harness de agente**: o que envolve o modelo (prompts, skills, ferramentas, laço de correção, fiscal);
- **harness de verificação**: o programa Python que o ESBMC verifica. O primeiro produz o segundo.

## Evidência que motivou

- **Rodada final (Fase 22):** das 742 hipóteses, 288 terminaram em `UNSUPPORTED`; o ESBMC deu veredito em 170.
- **Casos em que o harness mudou o comportamento** (`docs/experimentos/README.md`):
  - **ip_real_21:** o agente inventou uma classe `Other` sem `__len__`; o `TypeError` veio dela.
  - **bip_pandas_10:** a exceção nasceu dentro do stub `ndarray.__len__`.
  - **nm_real_11:** o motor de regras trocou `OrderedDict` por classe vazia; `len(self)` e `super().__setitem__`
    perderam o sentido. O mypy acusa as duas distorções (testado em 22/10 com `--python-typecheck`).
- **Teste A/B de 22/10** (5 bugs travados em `UNSUPPORTED`, agente com plugin do ESBMC, resultado parcial):
  o agente fez o ESBMC rodar em 3 de 5 com o corpo da função preservado, onde o motor de regras não rodou
  nenhum; nenhum bug confirmado ainda. No nm_real_12 o ESBMC disse seguro e o CPython reproduziu o bug
  (`ESBMC_MISSED`), o mesmo falso negativo do reprodutor 25 de `possiveis_problemas`.
  Pasta do teste: `/tmp/.../scratchpad/spike/` (descartável; os números entram no registro de experimentos
  quando completos).

## Objetivos

1. **Fazer o código real rodar no ESBMC** com o comportamento preservado no caminho do bug.
2. **Medir a preservação** por bug, em vez de confiar no agente ou num fiscal escrito à mão caso a caso.
3. **Aprender com o tempo:** o que destrava um caso vira conhecimento para os próximos, com aprovação da
   Fernanda.
4. **Acompanhar o ESBMC master:** quando o ESBMC passa a aceitar algo, o harness deixa de contornar.
5. **Transformar limitação do ESBMC em issue**, separando-a de defeito do harness.

## Não objetivos

- Melhorar a detecção (o LLM que aponta a linha). Este desenho começa com a hipótese pronta.
- Corrigir o ESBMC dentro deste repositório. Patches no ESBMC são outra frente (ver Restrições).
- Escolher o melhor modelo. O modelo é o mesmo nas comparações; o que muda é o harness.

## Anti-objetivos (falha mesmo que "funcione")

- **Confirmar um bug cuja exceção nasce do harness**, e não do código real.
- **O agente aprender sozinho a mexer muito:** nada entra no caderno de reparos sem a Fernanda aprovar.
- **Números que não se repetem:** uma rodada sem o commit do ESBMC e a versão das skills registrados não vale
  para a dissertação.
- **Trocar o motor de regras pelo agente sem medir:** a troca só acontece se o agente confirmar pelo menos
  tanto quanto o motor e distorcer menos, nos mesmos bugs.

## Como funciona

### Reaproveitar o que o ESBMC já tem

Decisão da Fernanda: **usar os agentes e o plugin do ESBMC como estão**, e escrever skill própria só para o que
eles não cobrem. O que já existe:

- **Plugin do ESBMC** (`esbmc-plugin`): a skill `esbmc-verification` e os comandos `/esbmc-plugin:verify` e
  `/esbmc-plugin:audit`. Já é o que o `/esbmc` usa no uso interativo que funciona bem.
- **Agentes do repositório do ESBMC** (`.claude/agents/` do checkout): `esbmc-verifier` e `creduce-reducer`.
  Conferidos na revisão de 22/10, **não servem como estão para a rodada medida**: o `esbmc-verifier` foi escrito
  para quem desenvolve o ESBMC (modo A corrige o código do próprio ESBMC até `VERIFICATION SUCCESSFUL`; modo B
  é firmware C/C++), pede confirmação ao usuário quando o modo é ambíguo (impossível em `claude -p`), fixa
  `model: sonnet` e tem metas que contrariam as regras do harness (acrescentar suposições e guardas). O
  `creduce-reducer` é para C/C++. **Decisão de quem escreveu:** a rodada medida usa só o plugin (cujo
  `/esbmc-plugin:audit` abre subagentes genéricos, que herdam o modelo); o `esbmc-verifier` fica para o
  consultor, que roda sob demanda; reprodutores Python continuam sendo reduzidos pelo script de redução por
  linhas usado em 22/10 nos reprodutores 46 e 47.
- **Conhecimento lido do checkout** (`verify/esbmc_knowledge.py`): README do frontend Python e testes de
  regressão que passam.

### Cérebro separado do motor

O **cérebro** são arquivos e código do repositório, independentes de quem roda o modelo. Por cima do que o
ESBMC já tem, entra só o que é desta pesquisa:

- **Regras do harness**, numa skill curta: corpo inalterado, stubs mínimos que não levantam exceção, sem
  `assert`, sem guarda na expressão suspeita (hoje no prompt de `verify/agent_arm.py`), e as pegadinhas do
  ESBMC-Python que o plugin não cobre (da skill pessoal `esbmc-python-guide` e de `verify/esbmc_python_notes.md`,
  conferidas contra o master atual antes de entrar).
- **O caderno de reparos aprendidos** (abaixo).
- **Conhecimento do ESBMC** lido do checkout em uso (`verify/esbmc_knowledge.py`, já existente), que se atualiza
  com cada `git pull` do master.
- **O fiscal** (abaixo), sempre em código, nunca no modelo.

O **motor** é quem chama o modelo:

- **Principal:** Claude Code em modo não interativo (`claude -p`), uma pasta por caso, com o plugin do ESBMC e
  as skills do projeto em `.claude/` da pasta. É o que `claude_agent()` em `verify/agent_arm.py` já faz,
  hoje sem as skills. Usa a assinatura, não o crédito da API.
- **Reserva:** API com uso de ferramentas (`ler_skill`, `rodar_esbmc`, `rodar_cpython`), o mesmo cérebro. Serve
  quando o limite da assinatura acabar e para comparar modelos ("o ganho vem do harness ou do modelo?").

### Self-healing

O agente roda o ESBMC, lê o erro e corrige o harness até haver veredito (o laço que o Claude Code já faz). A
diferença para hoje é o que ele tem à mão e o que fica registrado:

1. **A cada rodada do laço**, o agente recebe o erro do ESBMC e os trechos do conhecimento do checkout que
   casam com ele (`esbmc_knowledge.lookup`, já usado pelo `Healer` de `verify/healing.py`), mais as regras do
   harness e o caderno.
2. **Cada rodada é registrada**: o erro, o que o agente mudou (diff do harness) e o veredito seguinte. Esse
   registro é o que permite à Fernanda estudar a técnica caso a caso e é a fonte dos candidatos ao caderno.
3. **Os avisos baratos do fiscal rodam a cada rodada**, não só no fim: corpo alterado, stub que levanta exceção,
   erro novo de mypy. Assim dá para ver em que rodada o harness começou a mexer demais.
4. **Limite de rodadas e de tempo por caso**, e parada imediata quando o ESBMC cai (crash ou erro interno, como
   o `Healer` já faz desde o commit e070d8c): crash não se conserta no harness, vira reprodutor e candidato a
   issue.
5. **O que destravou vira candidato ao caderno** (abaixo), nunca regra direta.

### Teste executável a partir do contraexemplo (pytest do ESBMC)

O Lucas já trabalha com o gerador de testes do ESBMC
([pytest-testgen](https://esbmc.github.io/docs/python/pytest-testgen/)): com `--generate-pytest-testcase`, o
ESBMC transforma o contraexemplo num teste pytest que reproduz o bug (`--pytest-values-only` grava só os
valores). Entra no desenho em três papéis:

- **Prova executável do bug:** todo `CONFIRMED` vem acompanhado do teste pytest gerado pelo próprio ESBMC, que
  qualquer pessoa roda sem o pipeline. É o artefato que vai para o Lucas e para as issues.
- **Primeira entrada do teste diferencial:** o teste gerado roda no harness e no original (quando há ambiente
  real); os dois precisam falhar do mesmo jeito.
- **Substituto do contorno atual:** hoje `verify/pytest_gen.py` reescreve o programa como função solta porque,
  medido em 01/10 no 8.5, o gerador imprimia nomes internos (`x&0#1`) com receptor e perdia argumentos. Isso é
  remedido no master atual: se já funciona, o contorno sai; se não, vira reprodutor e issue, e o contorno fica
  até a correção.

### Caderno de reparos aprendidos

Cada vez que um caso destrava, o pipeline registra o par "erro do ESBMC → o que mudou no harness" como
candidato. A Fernanda revisa os candidatos (com o consultor ajudando a explicar cada um) e aprova o que vira
regra do caderno. Candidato que muda comportamento no caminho do bug é recusado. Regra cuja construção o
ESBMC master passou a aceitar sai do caderno.

### Consultor

Para casos travados, o `/esbmc` (Claude Code com o plugin, com as configurações da Fernanda) recebe o original,
o harness e o erro, e responde: por que travou (limitação do ESBMC ou defeito do harness), como faria rodar
sem mudar o comportamento, e que regra geral aprender. As respostas são material de estudo da Fernanda e fonte
de candidatos ao caderno; não decidem veredito. Limitação do ESBMC vira reprodutor em `possiveis_problemas` e
rascunho de issue.

### Fiscal

Roda depois do agente, sem LLM, e decide se a confirmação vale:

1. **ESBMC de novo** no harness, com o binário e as flags do pipeline.
2. **Replay no CPython** com os valores do contraexemplo, no corpo original (já existe).
3. **Teste diferencial:** original e harness rodam no CPython com as mesmas entradas (o teste pytest do ESBMC,
   o contraexemplo e mais entradas geradas). Se divergirem no caminho do bug (retorno, ou exceção e a linha onde
   nasce), a confirmação não vale. O resultado é um número por bug, por exemplo "concordou em 98 de 100
   entradas". **Em dois níveis (decisão da Fernanda):** onde o bug tem ambiente real que roda, o original roda com
   as dependências reais, e essa é a medida forte (quantos bugs têm esse ambiente ainda não foi medido; os 18
   casos "elegíveis" de 28/09 têm harness manual aprovado, o que é outra coisa); nos outros, roda contra os mesmos stubs e o bug sai marcado como "preservação não medida", nunca como
   preservado.
4. **Avisos baratos:** corpo preservado (`target_preserved`), exceção nascida em stub (`STUB_INDUCED`) e erros
   de mypy que o harness tem e o original não tem.

## Restrições

- **ESBMC:** sempre o master atualizado, compilado com Bitwuzla (`~/esbmc-master/build-bw`), com
  `--no-pointer-check --no-align-check`. Toda rodada registra o commit. Patches no ESBMC são desenvolvidos em
  outro checkout, nunca no que o pipeline usa para medir (em 22/10 um patch local de `async` contaminou
  `~/esbmc-master/build`).
- **Custo:** motor principal pela assinatura do Claude; o crédito da API (US$ 100) só para o motor reserva,
  com confirmação antes de rodar.
- **Ambiente:** WSL local, sem Docker; o repositório passa a morar no disco do Linux (`~/mestrado/llm_esbmc`).
- **Prazo:** qualificação até fevereiro de 2027; o desenho precisa render números comparáveis antes disso.
- **Registro:** cada rodada entra em `docs/experimentos/README.md` com data, pasta, commit, comando e
  resultado, mais o commit do ESBMC e a versão das skills e do caderno.

## Decisões tomadas por quem escreveu (a Fernanda pode mudar)

- Teste diferencial como critério principal de preservação; mypy só como aviso.
- Skills como arquivos no repositório, copiados para a pasta de cada caso, em vez de instalados no Claude Code
  da máquina, para que a rodada seja reprodutível.
- Primeiro passo de implementação: completar o teste A/B, ler as opiniões do consultor com a Fernanda, e só
  então escrever as skills, com o conteúdo vindo dos casos reais.
- Comparação final em dois braços nos mesmos bugs: motor de regras atual × harness de agente, medindo bugs
  confirmados (métrica final, dita primeiro) e preservação.

Respondidas pela conversa com a Fernanda:

- **O corpo da função pode mudar um pouco** ("recortar e reescrever um pouco é inevitável, o problema é mudar
  muito"). O critério é o teste diferencial, não o corpo idêntico: corpo alterado gera aviso e só confirma se o
  comportamento no caminho do bug for o mesmo (como o `CONFIRMED_SIMPLIFIED` de hoje). As regras do harness dizem
  isso ao agente.
- **O consultor roda sob demanda**, em casos escolhidos, não em todo caso travado. As opiniões são lidas com a
  Fernanda, e quem decide se é limitação do ESBMC ou defeito do harness é ela.

Tomadas por quem escreveu, depois da revisão:

- **Regra de confirmação:** qualquer divergência no caminho do bug, no contraexemplo ou nas entradas geradas,
  anula a confirmação. A taxa de concordância é relatada por bug, mas não há limiar de "maioria".
- **Comparação em amostra fixa:** os dois braços (motor de regras e harness de agente) rodam na mesma amostra de
  bugs com a hipótese na linha certa, sorteada antes e registrada, de tamanho que caiba no limite da assinatura
  (ordem de 30 bugs). O fiscal novo vale para os dois braços.
- **Caderno congelado:** o caderno aprende com casos fora da amostra medida (reprodutores, dataset da PGENE601,
  bugs não sorteados) e é congelado, com versão registrada, antes da rodada medida.
- **Um motor por rodada medida:** se o limite da assinatura acabar, a rodada pausa e retoma; não troca para a API
  no meio. O motor reserva é rodada própria.
- **Bugs de resultado errado (oráculo de valor) ficam fora** na primeira versão; o agente só trata exceções.

## Deixado para quem implementar

- Como gerar as entradas extras do teste diferencial (o pipeline já tem busca dinâmica em `verify/llm_input.py`
  e no braço `dynamic`).
- O formato do caderno de reparos e do registro de candidatos.
- Os limites de tempo por caso (o teste A/B usou 900 s por agente; dois casos estouraram).
