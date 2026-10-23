# Self-healing do harness guiado pelo repositório do ESBMC (item B, 19/10/2026)

Documento de trabalho da Fernanda. Substitui o escopo do item 6b do `docs/historico/PLANO_GERAL_2026-10-15.md`
(harness que aprende com o repositório do ESBMC) e o antecipa para agora.

## Intenção

A pesquisa é sobre **técnicas para o LLM acertar**, não sobre melhorar o ESBMC-Python. O ESBMC-Python está em
evolução pela equipe do Lucas; do lado da Fernanda cabe fazer o possível para o código real rodar nele.

Na rodada final (Fase 22 do `docs/experimentos/README.md`), o LLM aponta a linha certa em 153 de 277 bugs, mas
só 13 viram confirmação. A maior perda está depois da detecção: 101 bugs param em recusa do ESBMC e 9 em harness
não montado. Muitas dessas falhas trazem uma mensagem que diz o que consertar ("Add a type annotation",
`Object "tqdm" not found`, "precisa de tuple com 7 itens"), mas parte delas acontece antes de qualquer chamada
ao LLM e nunca recebe a chance de ser consertada.

O self-healing é o LLM recebendo o erro, mais o conhecimento atual do ESBMC tirado do próprio repositório dele,
e corrigindo o harness até o ESBMC dar um veredito. Como o ESBMC muda toda semana, o conhecimento vem do
checkout do ESBMC e se atualiza com um `git pull`, sem regra escrita à mão.

## O que já existe (não refazer)

- **Loop de reparo da spec** (`verify/loop.py`, `verify_hypothesis`): JSON recusado ou leitura `repairable` do
  ESBMC voltam ao LLM com a mensagem; `max_repairs=2`. Há a estratégia `resample` como linha de base.
- **Braço de agente** (`verify/agent_arm.py`): `claude_agent` (Claude Code com o plugin do ESBMC) e `api_agent`
  (8 rodadas sem ferramentas) escrevem `harness.py`. O pipeline refaz ESBMC e replay sozinho e classifica
  `CONFIRMED_SIMPLIFIED`, `STUB_INDUCED`, `FIXED_ALSO_FAILS`, `TARGET_ALTERED`. A rodada final não usou o agente.
- **Notas do ESBMC para o agente** (`verify/esbmc_python_notes.md`): escritas à mão, medidas no ESBMC 8.5.
- **Regras de reescrita com sonda** (`verify/rules.py`, `verify/capabilities.py`, `verify/probes/`): cada regra
  desliga sozinha quando a sonda mostra que o ESBMC instalado já aceita a construção.
- **Roteamento por classe de limite** (`verify/routing.py`, `limit_class`): grounding, contexto, harness, builder,
  limite do ESBMC.
- **Grafo de chamadas por AST** (`scan/callgraph.py`): no modo scan, cobre o repositório inteiro; no e2e do
  dataset, só o arquivo. Hoje serve para chamadores (detecção A12 e fatos da spec), não para o recorte.
- **Replay sem LLM** (`scripts/v2_replay_specs.py`) e **controle com a versão corrigida**
  (`scripts/v2_audit_control.py`).

## Objetivos

1. Dar uma chance de conserto pelo LLM às falhas que hoje terminam antes dele: `GROUNDING_FAILED`,
   `MISSING_DEPENDENCY` e `UNSUPPORTED` do `precheck`.
2. Alimentar todo conserto (loop de spec, novo conserto do precheck e braço de agente) com conhecimento tirado
   do checkout do ESBMC: trechos do `src/python-frontend/README.md` e testes de regressão que passam, escolhidos
   pela mensagem de erro.
3. Antes de pedir um stub ao LLM, trazer o código real da função chamada quando o grafo souber onde ela está.
4. Quando nada fizer o ESBMC rodar, guardar a hipótese como achado só do LLM, separado da métrica.
5. Medir quanto cada parte contribui, com ablação, para a dissertação.

## Não objetivos

- Mudar o ESBMC-Python ou abrir PR nele. Recusa que for limitação real vira linha na dissertação e, se valer,
  issue para o Lucas.
- Refazer a detecção. A medição usa as hipóteses e specs da rodada final.
- Extensão, plugin ou interface nova. Fica para depois da qualificação.
- Embeddings ou serviço de busca externo.

## Anti-objetivos (falha mesmo funcionando)

- **Confirmação inventada.** Um conserto que muda o comportamento do código e "acha" um bug criado pelo próprio
  LLM. Toda confirmação continua exigindo o replay no CPython sobre o **corpo original** da função, com os
  valores do contraexemplo, e o controle com a versão corrigida.
- **Mistura de números.** Achado só do LLM contado como confirmado.
- **Custo que não cabe na assinatura.** Conserto sem limite de rodadas.
- **Conhecimento congelado de novo.** Uma cópia manual do README que fica velha como as notas de 8.5.

## Desenho

O ciclo, para cada hipótese:

```
hipótese → grounding → recorte (B1: código real das funções chamadas) → stubs → spec do LLM → ESBMC
              │                │                                          │            │
              └── falhou ──────┴──────────── falhou ──────────────────────┴── recusou ─┘
                                             ↓
                     B2 conserto pelo LLM: erro + B3 conhecimento do ESBMC
                                             ↓
                         tenta de novo (até N rodadas no total)
                                             ↓
                  ainda sem veredito → B5 achado só do LLM (fora da métrica)
                  com veredito → replay no corpo original + controle (B4) → CONFIRMED ou não
```

### B1. Recorte com o código real das funções chamadas

Quando o recorte deixa um nome indefinido e o grafo (`CallGraph`) sabe onde ele é definido no repositório,
incluir essa definição no programa, recortada do mesmo jeito, em vez de virar stub. Limites: profundidade 2 e
tamanho máximo do programa; o que passar disso, ou o que vier de biblioteca de fora do repositório, segue para
stub. No e2e do dataset o grafo é de um arquivo só, então o ganho de B1 aparece no modo scan; no dataset ele só
não pode piorar nada.

### B2. Conserto pelo LLM nas falhas do precheck

Uma etapa nova, chamada quando o `precheck` devolve falha, antes de desistir da hipótese:

| Falha | O que o LLM recebe | O que o LLM devolve | Conferência do código |
|---|---|---|---|
| `GROUNDING_FAILED` | lista de funções do arquivo, código da função mais próxima, a hipótese | nome exato da função e expressão copiada do código | a expressão tem de existir literalmente na função; a hipótese original fica registrada |
| `MISSING_DEPENDENCY` | nomes indefinidos, como cada um é usado no recorte | stub em Python para cada nome (classe ou função tipada) | o stub não pode lançar exceção nem conter `assert`; um replay que quebra dentro do stub vira `STUB_INDUCED` |
| `UNSUPPORTED` do frontend | mensagem do ESBMC com a linha, trecho do recorte, conhecimento B3 | anotações de tipo, troca de stub ou simplificação fora do corpo da função alvo | corpo da função alvo igual ao original, salvo anotações na assinatura (mesma regra do braço de agente) |

Depois do conserto, o fluxo volta ao `precheck`. Recusas que o código classifica como limitação do harness
(`__new__`, `async`, construtor no oráculo de valor) também passam por aqui.

**Onde o conserto se aplica.** O `precheck` refaz o `ground()` a partir do arquivo a cada rodada, o que
apagaria o conserto. Os consertos ficam numa lista ordenada de edições sobre o recorte (o módulo do `Grounded`),
guardada junto da hipótese e reaplicada depois de cada `ground()`. O arquivo original nunca é alterado.

**Stubs escritos pelo LLM.** O stub declara o tipo de retorno e devolve um valor `nondet_*` desse tipo, como os
stubs de hoje. Valor concreto (`None`, `[]`, `0`) é proibido e recusado pelo código: senão o próprio stub
poderia empurrar a função alvo para a exceção sem quebrar ele mesmo.

**Grounding consertado e a métrica.** O conserto de grounding serve só para localizar a hipótese no código. A
métrica avalia a hipótese **original** do LLM com `at_bug_line`: se a original não estava na linha do bug, a
confirmação não conta, mesmo que a versão consertada caia nela. O relatório guarda as duas.

### B3. Conhecimento tirado do checkout do ESBMC

Um índice construído a partir do checkout apontado pelo ESBMC em uso (hoje `~/esbmc-master`):

- seções do `src/python-frontend/README.md` ("Features Supported by ESBMC-Python", "Limitations" e subseções);
- testes de `regression/python/*/` cujo `test.desc` é `CORE` ou `THOROUGH` (não `KNOWNBUG`), com `main.py`.
  São exemplos do que o ESBMC aceita hoje.

O índice guarda o commit do ESBMC e é refeito quando o commit muda. A busca é lexical: palavras da mensagem de
erro mais os nomes das construções da linha recusada (tipos de nó do AST, nomes de métodos). O LLM recebe no
máximo 2 trechos do README e 3 testes, com limite de caracteres. O mesmo bloco entra no loop de spec, no B2 e,
no lugar das notas de 8.5 ou junto delas, no braço de agente.

### B4. Portão de confirmação

Não muda a regra, só passa a valer também para o B2: confirmação exige replay no CPython do **corpo original**
com os valores do contraexemplo, exceção igual à da hipótese e controle com a versão corrigida. "Corpo original"
quer dizer a função alvo exatamente como no arquivo; o que estiver em volta dela pode ter sido consertado, e
por isso a exceção tem de nascer dentro da função alvo. Exceção que nasce em código escrito ou editado pelo LLM
vira `STUB_INDUCED`, como no braço de agente. O relatório
guarda o diff entre o recorte original e o consertado e quantas rodadas foram gastas.

### B5. Achado só do LLM

Quando todas as rodadas acabam sem veredito do ESBMC, a hipótese recebe um status próprio, por exemplo
`LLM_ONLY`, com o motivo final (limitação do ESBMC, harness, dependência). Entra no relatório e no funil numa
linha separada e nunca soma na métrica de confirmados. Se o braço dinâmico do orquestrador tiver evidência no
CPython (`FUZZ_FOUND`), ela aparece junto.

## Pré-requisitos (antes de medir)

1. O witness de string (`verify/string_witness.py`) volta vazio no ESBMC master `5d17828`
   (`tests/test_verify_string_witness.py` falha). O replay de hipóteses com `nondet_str()` depende dele.
2. `tests/test_verify_esbmc_integration.py::test_probes_on_master_keep_the_rules_its_known_gaps_need` falha
   porque o master passou a aceitar `metodo_append`: atualizar a expectativa.
3. Fixar o ESBMC dos experimentos: master `5d17828` (wrapper `~/esbmc-master/esbmc.sh`).

## Medição

Base: hipóteses **na linha do bug** de bugs ainda não confirmados, da rodada final, que pararam em grounding,
dependência, recusa ou spec. O ponto de partida é a tabela de `docs/historico/6b_base_recusas_2026-10-19.md`
(96 hipóteses em 73 bugs só de recusa), somada às de grounding e dependência.

Rodadas com as specs já salvas e LLM só onde o conserto pede. As hipóteses que pararam antes da spec não têm
spec salva: depois do conserto, elas recebem uma chamada de spec nova. Uma spec salva que deixa de valer depois
do conserto (pede um nome que sumiu ou falta um novo) também é refeita. Por isso cada braço tem uma estimativa
de chamadas antes de rodar.

| Braço | O que muda | Separa |
|---|---|---|
| 0 | replay no master, sem B | ganho do ESBMC novo |
| 1 | B2 sem B3 | conserto pelo erro sozinho |
| 2 | B2 + B3 | contribuição do conhecimento do repositório |
| 3 | braço 2 com `resample` | conserto guiado contra tentativas independentes |

No braço 3, o bloco do B3 é escolhido uma vez, pela primeira recusa, e fica fixo; o LLM não vê a tentativa
anterior nem o erro dela. Assim o braço 3 difere do 2 só no retorno do erro.

Medidas por braço: bugs que chegam a um veredito do ESBMC, **bugs confirmados na linha** (métrica principal),
bugs novos na métrica, rodadas e tokens gastos, rejeitados por `STUB_INDUCED`, `FIXED_ALSO_FAILS` ou
`TARGET_ALTERED`, e quantos ficaram `LLM_ONLY`. Cada rodada é registrada no `docs/experimentos/README.md` com
data, pasta, commit e comando.

## Aplicação em repositório real

Depois do dataset, o modo scan roda com e sem o B nos dois primeiros repositórios da primeira leva de
`docs/pgene601/pgene601_repos_scan_2026-10-19.md`: Adafruit_CircuitPython_GPS e pynmea2. Com o grafo do
repositório inteiro, o B1 traz o código real das funções chamadas de outros arquivos. Sem gabarito, a medida é:
funções que chegam a um veredito do ESBMC, achados `CONFIRMED` que sobrevivem à leitura manual (o contexto real
de chamada permite a entrada do contraexemplo) e achados `LLM_ONLY`. A detecção roda uma vez por repositório e
os dois braços reaproveitam as mesmas hipóteses.

## Restrições

- LLM pelo `claude_cli` (assinatura). Antes de cada rodada, estimar chamadas e avisar.
- Trabalho direto no `master` deste repositório; commit só quando a Fernanda pedir.
- Um item por vez, seguindo o PLANO_GERAL; ideia nova vai para "Depois".
- Qualificação até fevereiro de 2027: o número do B precisa estar fechado em novembro, para dezembro ser texto.

## Decidido pela Fernanda

- O nome é **self-healing**.
- Quando o ESBMC não roda, fica o resultado só do LLM.
- O conhecimento vem do repositório do ESBMC e acompanha a evolução dele.
- O grafo deve trazer o código real das funções chamadas.
- Extensão fica para depois; o pipeline segue pela CLI.
- O dataset serve para validar o método; o objetivo é aplicar em repositórios reais. Por isso o B1 entra agora
  e o B é medido também no modo scan, em repositório real (seção "Aplicação em repositório real").
- O braço de agente fica fora dos braços de novembro; só recebe o bloco do B3 junto das notas de 8.5.
- Para depois da qualificação, junto da extensão: braço de agente na medição e code smells como camada só do
  LLM (já anotado no "Depois" do PLANO_GERAL).

## Escolhas minhas (a conferir)

- Limite de 3 rodadas de conserto por hipótese no B2, além das 2 do loop de spec.
- Profundidade 2 no B1.
- Busca lexical no B3, sem embeddings; 2 trechos do README e 3 testes.
- O status `LLM_ONLY` como nome; pode ser outro.
- Ablação em 4 braços, para a dissertação mostrar a contribuição de cada parte.
- Consertos como lista de edições sobre o recorte, reaplicada a cada `ground()`.
- Stub do LLM só com retorno `nondet_*`.
- Métrica pela hipótese original quando o grounding foi consertado.
- No braço 3, bloco do B3 fixo pela primeira recusa.

## Deixado ao implementador

- Formato do índice B3 e onde ele fica em disco (fora do repositório do ESBMC).
- Como escolher as construções da linha recusada para a busca.
- Organização em módulos, desde que siga o estilo de `verify/`.
- O prompt exato do B2, desde que proíba mudar o corpo da função alvo e exija expressão copiada no grounding.
