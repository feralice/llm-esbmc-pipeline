# Auditoria 2: AST grounding, gabarito e validade das métricas (16/11/2026)

Documento de trabalho para a Fernanda. Escrito por IA (Claude Code), em modo somente leitura: nenhum teste, pipeline, ESBMC ou LLM foi executado. Os números da Parte C saíram de scripts Python que só leram os JSON das rodadas e os arquivos do dataset (rascunho em `/tmp/claude-1000/-home-fernanda-mestrado-llm-esbmc/fd7a2316-c270-40e8-bfa8-1fc8127162f2/scratchpad/an.py`). As decisões sobre o que fazer com os achados são suas.

Marcadores: **[F]** fato conferido no código ou no artefato; **[I]** inferência a partir de fatos; **[H]** hipótese ainda não testada; **[NV]** não verificado.

**O que li no código (linha a linha):** `verify/grounding.py` inteiro; `verify/astutil.py` (busca de função e de expressão, l.18-277); `v2_evaluator.py` inteiro; `verify/report.py` l.57-130; `verify/outcome.py` l.1-143; `verify/replay_worker.py` l.180-255; `verify/render.py` l.130-160 e l.484-590; `verify/compat.py` (`cut_after_suspect` l.620-670, `none_guards` l.675-813, cabeçalho de `async_to_sync`); `verify/healing.py` l.125-210 e l.360-531; `verify/loop.py` l.295-330 e l.420-520; `verify/hypothesis.py`; `llm/example_pool.py`; `scripts/build_disciplina_pgene601.py` (cabeçalho, primeiro item de `SPECS`, l.883-1041); `scripts/gabarito_funcoes.py` e `scripts/patch_rule.py` inteiros; cabeçalho de `scripts/propose_crash_lines.py`.

**O que li só por busca dirigida (grep), sem leitura completa:** `verify/spec.py`, `verify/caller_facts.py`, `llm/prompts.py`, `verify/context.py`, `verify/dead_guards.py`. Procurei leituras de arquivo e os nomes dos campos do gabarito; o resultado está na seção 2.7. **[NV]:** `scripts/build_v2_bugsinpy.py` (não lido; trata de `bugs_reais`, fora da rodada dos 47).

**O que só vi em documentos:** as auditorias anteriores de 16/11, `dataset/disciplina_pgene601/README.md`, `docs/projeto/REGRA_DE_ACERTO_2026-11-14.md`, `resumo.md` da rodada de 11/11.

**Não repito** o que as auditorias anteriores já cobriram: o "apontado" que vale 47/47 por construção, a falta de negativos, a troca de assinatura no pymodbus_2921, a contaminação dos 47 e os intervalos de confiança. Aqui eu aprofundo a ligação entre hipótese, código e rótulo.

---

## Resumo em dez pontos

1. **[F] O grounding não sabe nada do bug.** Ele confere se o texto que a LLM chamou de suspeito existe, com a mesma árvore sintática, dentro da função nomeada (`astutil.py:241-259`). Qualquer expressão que exista na função passa. O grounding garante "esta expressão está no código", nunca "esta expressão é o defeito".
2. **[F] Nenhum campo do gabarito chega à detecção, ao harness ou ao reparo** na rodada de 16/11. A única fonte de vazamento de localização é estrutural e já conhecida: o arquivo de entrada só tem as funções rotuladas.
3. **[F] Os 5 bugs com `expected_type = struct.error` não podem ser contados como reproduzidos, em nenhuma rodada.** O replay grava `type(exc).__name__`, que para `struct.error` é `error`. Além disso, o harness troca `struct` por uma classe que devolve valores não determinísticos e nunca levanta erro. O teto real é 42, não 47.
4. **[F] Dos 13 bugs "apontados e reproduzidos", 11 reproduzem na linha da expressão rotulada ou do ponto de estouro. 2 (piouart_6, pycomm3_331) reproduzem outra falha com o mesmo tipo de exceção.** As mensagens mostram isso: `memoryview: a bytes-like object is required, not 'list'` e `bytes must be in range(0, 256)`, que não são o defeito corrigido pelo patch.
5. **[F] Os 8 confirmados estão todos na linha rotulada ou no ponto de estouro.** O ESBMC e o replay falham na mesma linha do programa em 7 dos 8. No oitavo (blinka_434), a violação do ESBMC fica num ajudante que o próprio pipeline insere antes da expressão suspeita (`none_guards`). Só 5 dos 8 batem com o campo `expression`. Outros 2 batem só com `crash_expressions`, numa função que o patch não alterou. O último (gps_126) fica na linha certa, mas o comparador não reconhece a expressão.
6. **[F] Existem dois "8 de 47" diferentes no mesmo relatório.** O `by_function.confirmado_esbmc` dá 8. O `confirmed_by_location.expression_equivalent` também dá 8, mas o conjunto é outro: inclui pymodbus_2980 (confirmado com IndexError, quando o rótulo pede struct.error) e deixa de fora gps_126. Quem citar "8" precisa dizer qual dos dois.
7. **[F] 5 das 13 hipóteses CONFIRMED têm exceção diferente da esperada** (gps_127, mavproxy_1032, mavproxy_881, pymodbus_1738, pymodbus_2980). O veredito CONFIRMED não usa o gabarito. Ele diz "o harness quebra assim", não "este é o bug".
8. **[F] O comparador de expressões erra nos dois sentidos.** Falso negativo: hipótese com vários comandos separados por `;` e rótulo que é só um nome (`signals`) ou um atributo (`app.DiscoveryUrls`). Falso positivo: rótulo de estouro longo, em que qualquer pedaço conta. Exemplo: em mavproxy_1032, `int(gps_lat * 10000000.0)` casa com a chamada `gps_input_send(...)` inteira.
9. **[F] Entradas `bytes` só podem valer `b"ab"` ou `b""` no harness** (`render.py:146-147`). Bugs que precisam de um buffer longo ou de um conteúdo específico ficam fora do alcance. Os bugs de buffer confirmados são todos "buffer vazio".
10. **[F] O reparo (healing) pode trocar a expressão suspeita**, e a métrica continua pontuando a hipótese original (`healing.py:497-498` e `:507`). Em 16/11 isso aconteceu 2 vezes. Uma delas, mavproxy_1447 `3fecf2adbc3d`, entrou nos reproduzidos com a exceção numa linha que não é a da hipótese.

---

## 1. Arquitetura do grounding (Parte B)

### 1.1 Fluxo real, do arquivo à linha do replay

1. **Detecção.** A LLM lê `funcao_com_bug/<id>.py` e devolve `function`, `suspect_expression` e `trigger_condition`. **[F]** O campo `line` é sempre 0 nas 106 hipóteses de 16/11. A conversão `BugHypothesis.from_candidate` usa o padrão `line=0` (`scan/pipeline.py:446`, `hypothesis.py:39-48`). **[F]** O texto passa por `undo_prompt_rename`, que só troca `target_function` pelo nome real (`hypothesis.py:15-18`).
2. **Troca de arquivo.** `verification_source` procura um arquivo de mesmo nome em `verification_sources` (`loop.py:425-431`). Na rodada, isso é `arquivo_com_bug` (configuração `verification_sources` no `v2_verify_report.json`) **[F]**. A detecção vê o recorte, e o grounding usa o arquivo inteiro. A ligação entre os dois é só o nome do arquivo e o nome qualificado da função.
3. **`ground()`** (`grounding.py:632-761`):
   - `ast.parse` do arquivo inteiro; falha vira `GroundingFailure` (l.635-638).
   - `find_function`: função de módulo ou método de classe de módulo, definido **uma única vez** (`astutil.py:18-33`). Quando não acha, tenta nesta ordem: versão síncrona de `async def` (`async_to_sync`, l.645), função externa que leva à aninhada (`outer_entry`, l.651), içar a aninhada para o nível do módulo (`_hoist_nested`, l.657). Se nada der certo, devolve `GroundingFailure`.
   - **Casamento da expressão** (`expression_nodes`, l.672): ver 1.2. Sem casamento: `"suspect expression not found in ..."`.
   - Com `h.line`, fica só a ocorrência mais próxima da linha (l.675-676). Com `line=0`, que é o caso de todas as hipóteses, **todas as ocorrências** viram spans (l.677).
   - Depois vem a montagem do contexto: herança copiada para a classe (l.693-701), decoradores apagados sem mudar a numeração (l.703-704, `_strip_decorators`), `fold_dead_guards` (l.706), `context_module` (l.708), `prune_class`, `reslice`, `remove_unused` e `stub_imports` (l.711-730).
4. **Render** (`render.py:496-590`):
   - Os spans são deslocados para a numeração do programa (`shift`, l.547-548).
   - O **programa do ESBMC** passa por `rewrite_compat`, `drop_project_decorators`, `split_conditional_assignments`, `rename_builtin_named_methods`, `cut_after_suspect`, `remove_unused`, `none_guards` e `nondet_clock` (l.550-567).
   - O **programa do replay** é o mesmo cabeçalho com outro driver, **sem** essas reescritas (l.522-532). As linhas em branco no lugar dos stubs de exceção mantêm a numeração igual (l.530-532).
   - Os spans do programa reescrito são recalculados por `_suspect_spans` (l.560), que procura a mesma expressão de novo. Se não achar, ficam os spans antigos (`or spans`).
5. **Replay** (`replay_worker.py:222-255`): "reproduced" quer dizer que o último quadro da pilha dentro da função alvo está numa linha de algum span (l.246-248). Qualquer outra exceção vira "other_failure". O tipo gravado é `type(exc).__name__` (l.250).
6. **Veredito** (`outcome.py:126-143`): CONFIRMED exige violação do ESBMC, replay "reproduced" e tipo do replay dentro do conjunto de exceções que o ESBMC reportou. **[F]** A linha da violação do ESBMC não é comparada com o span.

### 1.2 Como a expressão é casada

- `_readings` (`astutil.py:211-222`) gera variantes do texto: o texto original, o texto sem a palavra de bloco (`if `, `elif `, `while `, `return `, `assert `) e sem os dois-pontos finais, e cada pedaço separado por `;`.
- `_matching` (`astutil.py:241-259`) tenta ler a variante como expressão. Se não der, tenta como um único comando, ou como cabeçalho de `for`/`with`. Depois compara `ast.dump(..., include_attributes=False)` com **todos os nós** da função. É igualdade estrutural exata, sem posição. Espaços e aspas não importam, mas `x+1` e `1+x` são diferentes.
- A primeira variante que casa ganha. **[I]** Consequência: para `hours = int(time_utc[0:2]); mins = ...; secs = ...` (gps_126), o grounding usa a primeira atribuição. Para `if signals:` (cantools_804), usa o nome `signals`, que casa com **toda** leitura de `signals` na função.

### 1.3 Transformações que mudam posição ou expressão

| Transformação | Onde | Muda a linha? | Muda o que o ESBMC checa? |
|---|---|---|---|
| Decoradores apagados | `grounding.py:499-512` | não (linhas em branco) | sim, o corpo roda sem o decorador |
| `fold_dead_guards` | `dead_guards.py:1-6` | não | ramos mortos viram `pass` |
| Herança copiada para a classe | `grounding.py:355-384` | não (vai depois da classe) | membro da base passa a ser do receptor |
| `async_to_sync` | `compat.py:994-997` | não (diz manter a linha) | `await x` vira `x` |
| `_hoist_nested` | `grounding.py:561-602` | **sim**: a função vai para o fim do módulo e `line` é recalculada | variáveis livres viram parâmetros |
| `cut_after_suspect` | `compat.py:634-670`, só no programa do ESBMC | não | **sim**: o caminho termina depois da instrução suspeita (`pass` ou `__ESBMC_assume(False)`) |
| `none_guards` | `compat.py:765-813`, só no programa do ESBMC | não (mesma linha, com `;`) | **sim**: insere `_esbmc_none_attribute(x is None)`, que **levanta** AttributeError ou TypeError explicitamente |
| `split_conditional_assignments` | `render.py:555-556` | **sim**, só no programa do ESBMC (o range é recalculado, l.579-583) | divide atribuições |
| Reparo (healing) com edição no corpo | `healing.py:181-199`, `:493-495` | pode mudar | o ESBMC vê o corpo simplificado; o replay vê o corpo original, menos as edições simplificadoras |

Exemplo concreto do `none_guards` **[F]**: em `programs/560d455ab903_a0.py` (blinka_434), a linha 55 virou `_esbmc_none_attribute(self._pwmpin is None); self._pwmpin.stop()`. As linhas 2-5 definem o ajudante, com `raise AttributeError(...)`. A violação que o ESBMC reportou está na **linha 4, função `_esbmc_none_attribute`** (log em `programs/560d455ab903_a0/esbmc_unwind5/esbmc_outputs/560d455ab903_a0_6c95fcf1fc_direct.log:68-70`). Ou seja, o ESBMC provou que `self._pwmpin` pode ser None naquele ponto. O tipo de exceção foi escrito pelo pipeline, não deduzido pelo modelo de semântica Python do ESBMC.

### 1.4 Falhas, fallbacks, aceitação e rejeição

- **[F]** Na rodada de 16/11, o veredito final GROUNDING_FAILED tem contagem 0 (`verification.by_verdict`). Houve 2 falhas de grounding na primeira tentativa, as duas "suspect expression not found", e o reparo resolveu as duas trocando a expressão:
  - `3fecf2adbc3d` (mavproxy_1447): de `self.per_cell[id], self.current_battery[id], self.battery_level[id]` (os três argumentos de um `%`, que não existem juntos como nó) para `self.current_battery[id]`.
  - `07b31d307bd4` (pythoncan_1599): de `for i in output_json if i['link_type'] == 'can'` (pedaço de compreensão) para a compreensão inteira.
- **[F]** O reparo de grounding (`healing.py:397-412`) mostra à LLM a lista de funções do arquivo e o código da mais parecida, e pede "function" e "expression" para "a mesma suspeita". Aceita qualquer par que exista no código (l.409-411). Ninguém confere se a nova expressão é a mesma suspeita.
- **[F]** O resultado final volta a carregar a hipótese original (`healing.py:507`), e a avaliação por função usa `r['hypothesis']` (`v2_evaluator.py:313`). Se o reparo mudar de **função**, a métrica pontua a função antiga com o replay da nova. **[I]** Em 16/11 as duas trocas ficaram na mesma função, então o número por função não mudou. O risco existe no código.
- **[F]** O build do dataset usa o mesmo `expression_nodes` para validar os rótulos (`build_disciplina_pgene601.py:29`, `:907-913`). Gabarito e grounding falham juntos se essa função tiver um defeito. É uma dependência comum, não uma validação independente.

### 1.5 Veredito da Parte B

**[F]** O grounding identifica **um trecho sintaticamente presente na função nomeada**. Ele não usa o patch, a exceção nem o contexto do defeito, por desenho: isso evita vazamento. Quem liga a hipótese ao defeito é o replay: a exceção tem de nascer nos spans da expressão. Como `line=0`, os spans cobrem todas as ocorrências. Quando a expressão é um nome curto (`signals`), o span cobre várias linhas. **[I]** O grounding é um filtro de "não inventou código", e só isso. Não serve como evidência de localização correta.

---

## 2. Esquema real do gabarito (Parte A)

### 2.1 Onde ficam os rótulos [F]

| Arquivo | Conteúdo | Usado por |
|---|---|---|
| `dataset/disciplina_pgene601/manifest.json` | 47 itens, `detection_file = funcao_com_bug/...` | avaliação (`v2_evaluator.py:240-260`, `verify/report.py:57-66`) |
| `ground_truths.json` | os mesmos itens, com `file` no lugar de `detection_file` | só a checagem de IDs iguais (`v2_evaluator.py:248-249`); pool de exemplos A13 (não usado em 16/11) |
| `manifest_full.json` | `detection_file = arquivo_com_bug/...` | não usado na rodada de 16/11 [I] |
| `gabarito_funcoes.json` | funções tocadas pelo patch | tabela das funções irmãs (`v2_evaluator.py:268-270`) |
| `patches/*.diff` | diff unificado buggy → corrigido | `gabarito_funcoes.py`; leitura humana |

### 2.2 Como os rótulos foram derivados [F]

- **Fonte humana.** `function`, `expression`, `crash`, `expected_type`, `kind`, `category`, `source` (origem do rótulo) e `note` estão **escritos à mão** na lista `SPECS` de `scripts/build_disciplina_pgene601.py` (ex.: l.50-66). O valor `review: patch_lido` (l.993) diz que o rótulo veio da leitura do patch.
- **Checagens automáticas do script** (l.948-967):
  1. a expressão rotulada existe na função do arquivo com bug e no recorte (`_grounded`, com `expression_nodes`);
  2. cada `crash` existe na função;
  3. o patch toca a expressão: reescreve a linha (`linha_alterada`) ou insere logo antes ou depois (`insercao_adjacente`) (`_patch_touch`, l.916-935). Se não tocar, o script aborta.
- **[F] O resultado de `_patch_touch` só é impresso** (l.963-965). No manifesto vai o `source` declarado à mão (l.990). Não conferi se as duas classificações concordam nos 47 **[NV]**.
- **[F] `expected_type` não é verificado por execução.** Nada no script roda a versão com bug para ver a exceção. O tipo vem da leitura do PR e da issue.
- **[F] `line`** é a linha da primeira ocorrência tocada no **arquivo com bug inteiro** (l.931-934, l.988). Em 45 dos 47 itens, essa linha passa do tamanho de `funcao_com_bug/<id>.py`, ou seja, está em outra numeração que a do arquivo que a LLM lê. A avaliação atual não usa `line`, então isso não afeta os números. Afeta quem tentar comparar linhas sem converter.
- **[F] `propose_crash_lines.py` não gerou os rótulos dos 47.** Ele aponta para `dataset/bugs_reais` (l.20-24). Os `crash_expressions` dos 47 vêm do campo `crash` de `SPECS`.
- **[F] `gabarito_funcoes.py`** lê o diff, pega as linhas antigas alteradas ou vizinhas de inserção e devolve a função mais interna que contém cada uma (l.20-88). É um derivado, sem decisão humana.

### 2.3 O que um rótulo representa [F]

| Campo | Significado | Unidade |
|---|---|---|
| `detection_file` | recorte só com as funções rotuladas, sem imports (ex.: `funcao_com_bug/cps_pymodbus_2980.py` começa em `class ReadFileRecordRequest:` e usa `struct` sem importar) | arquivo |
| `function` | 1 ou 2 nomes qualificados separados por `/` (6 itens com duas funções) | função |
| `expression` | um nó da AST: expressão (33) ou comando (14) | expressão |
| `line` | linha no arquivo inteiro, não no recorte | linha |
| `crash_expressions` | onde estoura, quando é longe da causa; existe em 18 itens e falta em 29 | expressão |
| `expected_type` | nome da exceção, às vezes qualificado (`struct.error`) | tipo |
| `failure_kind`, `failure_kind_note` | se o ESBMC pode modelar; descrição livre do comportamento | texto |
| `categories` | 1 categoria, rotulador único | classe |

**[F]** Distribuição de `expected_type`: TypeError 10, IndexError 7, AttributeError 7, ValueError 6, **struct.error 5**, UnboundLocalError 4, KeyError 4, ZeroDivisionError 3, UnicodeDecodeError 1. Não há rótulo de **comportamento** (entrada que dispara a falha, ou caminho de chamada). O gabarito diz onde e qual exceção, nunca com qual entrada.

### 2.4 Rótulos com várias linhas ou várias funções [F]

- Duas funções: opcua_1131, pythoncan_1811, mavproxy_881, ros2cli_1026, gps_60 e gpiozero_716. Em 5 delas, uma das funções rotuladas **não é tocada pelo patch**. É a função onde o programa estoura (`gabarito_funcoes.json`: pythoncan_1811 `_process_fd_can_frame`, mavproxy_881 `check_read_send`, ros2cli_1026 `NetworkReport.report`, gps_60 `_parse_talker`, gpiozero_716 `CPUTemperature.value`).
- Expressão que aparece mais de uma vez na função: cantools_804 (`signals`, 2 vezes) e pyserial_820 (2 vezes).
- Rótulo de várias linhas: pycomm3_331 (linhas 36-38). O `crash_expressions` do mavproxy_1032 é uma chamada de 7 linhas.
- Os 3 itens async (opcua_1131, opcua_1955, opcua_1826): `find_function` não os encontra no arquivo inteiro, porque devolve None para método async (`astutil.py:31`). Para eles, só o caminho `async_to_sync` funciona.

### 2.5 Guardas adicionados pelo patch [F]

13 rótulos não são a linha alterada. São o comando vizinho de um guarda inserido: `statement_after_insertion` 10 e `statement_before_insertion` 3. Desses 13, 10 têm `crash_expressions` e 3 não têm (pymodbus_2921, mavproxy_1572, mavproxy_1447). Nesses três, o comando vizinho por acaso **é** o ponto de estouro. Nos outros, o rótulo `expression` pode não ter relação com o defeito:
- mavproxy_1032: `now = time.time()` é a primeira linha depois de `if self.master is None: return`;
- gps_60: `data_type = bytes(data_type.upper(), "ascii")` é a linha depois de `if len(data_type) < 5: return False`;
- gpiozero_716: `self.min_temp = min_temp`, no `__init__`, é a linha depois do guarda `if min_temp >= max_temp: raise ValueError`.

**[I]** Nesses casos, uma hipótese "na expressão rotulada" é uma hipótese numa linha que o patch não considerou defeituosa. A métrica por expressão conta isso como acerto. Exemplo real: `499740aa20e7` (gps_60, LLM_ONLY), que suspeita de UnicodeEncodeError em `bytes(data_type.upper(), 'ascii')`. O comparador conta como acerto no rótulo, mas é outro defeito.

### 2.6 Erros e ambiguidades [F]

- A ressalva do pymodbus_2980 cita `ReadFileRecordResponse.decode`, mas `gabarito_funcoes.json` mostra que o patch toca `WriteFileRecordRequest.decode` e `ReadFifoQueueResponse.decode` (já registrado na Auditoria 0).
- pymodbus_2980: o patch troca `byte_count = int(data[0])` por `if (byte_count := int(data[0])) > len(data) - 1: raise ...` (`patches/cps_pymodbus_2980.diff`). **[I]** Com `data = b""`, `int(data[0])` continua levantando IndexError **depois** da correção. Uma hipótese "IndexError em `int(data[0])` com buffer vazio" está na expressão rotulada, mas descreve uma falha que o patch não corrige. É o caso da hipótese `f330a5b2a35a`, CONFIRMED (seção 5).
- Rótulos que são só referência: cantools_804 (`signals`) e opcua_671 (`app.DiscoveryUrls`). O comparador ignora nome, atributo e constante como subexpressão (`v2_evaluator.py:67-76`). Rótulos assim só casam por igualdade direta ou depois de tirar `if`/`return`. `for url in app.DiscoveryUrls:` não casa com `app.DiscoveryUrls`.
- `struct.error`: ver seção 4.1.

### 2.7 O gabarito influencia detecção, harness ou reparo?

Busca por `ground_truth`, `manifest`, `expected_type`, `crash_expressions`, `cause_expressions`, `gabarito`, `label_sources` e `failure_kind` em `src/research_pipeline` **[F]**:
- aparecem em `v2_evaluator.py`, `verify/report.py` e `maintenance/gate.py` (avaliação), em `v2_eligibility.py` e `dataset_audit.py` (montagem e auditoria de dataset) e em `llm/example_pool.py`;
- **não aparecem** em `grounding.py`, `healing.py`, `spec.py`, `caller_facts.py`, `render.py`, `compat.py`, `loop.py` nem `prompts/`;
- em `spec.py` e `caller_facts.py`, as únicas leituras são a resposta JSON da LLM e o código-fonte recebido (`spec.py:113`, `caller_facts.py:134`, `:383`).

`llm/example_pool.py` é a exceção que pede atenção. A variante A13 monta exemplos few-shot a partir de um `ground_truths.json`, com `expression`, `crash_expressions` e `failure_kind_note` (l.87-106). Exclui só o mesmo arquivo e o mesmo projeto (l.109-115). **[F]** A rodada de 16/11 usou `v2_variants = ['A1', 'A2']`, sem A13. **[I]** Se A13 for ligada nos 47, a LLM vê rótulos de outros bugs do mesmo conjunto (por exemplo, rótulos de MAVProxy quando analisa pymavlink, que são projetos diferentes). Isso seria vazamento entre itens.

### 2.8 Risco de vazamento para os prompts

| Canal | Leva rótulo? | Evidência |
|---|---|---|
| Recorte `funcao_com_bug` | **sim, a função**: o arquivo só tem as funções rotuladas | `build_disciplina_pgene601.py:883-904`; Auditoria 0 |
| Recorte sem imports | não leva rótulo, mas tira contexto | `funcao_com_bug/cps_pymodbus_2980.py:1` |
| Contexto de chamadores (`spec_context = callers`) | não; vem do arquivo com bug | config da rodada |
| Reparo (healing) | não; vê o código, a mensagem do ESBMC e as lições | `healing.py:414-435` |
| Lições automáticas (`lessons`) | **[H]** podem carregar texto de casos anteriores dos 47, porque foram aprendidas neles | `healing.py:350-363`; não li o conteúdo das lições |
| A13 | sim, se ligada | seção 2.7 |
| `arquivo_corrigido` | só para hipótese de valor (`loop.py:434-439`); nenhuma em 16/11 | `oracle` vazio nas 106 |

### 2.9 Deslocamento de linha

- **[F]** Há três numerações: recorte (detecção), arquivo inteiro (grounding e `line` do manifesto) e programa gerado (replay e ESBMC).
- **[F]** O replay grava a linha do programa e o `target_range`. Converti para a numeração do arquivo com `linha_programa - target_range[0] + def_da_função` e conferi o texto nos casos em que o programa de replay estava salvo: 36 conferências certas e 1 errada. A errada é `3fecf2adbc3d`, em que o caminho do programa salvo pertence a outra tentativa. Com a mensagem `KeyError '0'`, a conversão para a linha 54 está coerente.
- **[F]** O `split_conditional_assignments` só mexe no programa do ESBMC. Por isso, linha do ESBMC e linha do replay podem divergir quando essa regra atua (`render.py:579-583`).

### 2.10 O que é "acerto de localização" hoje

- **[F]** Pela regra de 14/11, a localização **não decide** o acerto. O "apontado" é por função, e a expressão fica como apoio (`REGRA_DE_ACERTO_2026-11-14.md`).
- **[F]** Na prática, o nível "apontado e reproduzido" mistura dois critérios:
  - `reproduced`: exceção dentro dos spans da hipótese;
  - `other_failure` com a linha em qualquer ponto da função (`v2_evaluator.py:281-290`).

  O segundo não exige que a hipótese esteja certa.
- **[I]** Não existe hoje nenhuma métrica que exija ao mesmo tempo (a) hipótese na expressão rotulada ou no ponto de estouro, (b) exceção na linha rotulada e (c) tipo esperado. A seção 3 propõe essa matriz e a calcula.

---

## 3. Matriz de critérios de acerto (Parte C)

### 3.1 Avaliadores existentes [F]

| Métrica no JSON | Código | Unidade | Critério |
|---|---|---|---|
| `by_function.apontado` | `v2_evaluator.py:311` | bug | hipótese numa função do rótulo |
| `by_function.apontado_e_reproduzido` | `:315-318` | bug | + replay com `exception_type == expected_type`, `reproduced` ou `other_failure` dentro da função |
| `by_function.confirmado_esbmc` | `:319` | bug | + alguma dessas hipóteses com CONFIRMED |
| `detection_by_location.expression` | `:198-204` | bug (tp) / hipótese (fp) | texto idêntico ao `expression` ou a um `crash_expressions` |
| `detection_by_location.expression_equivalent` | `:205-211` | idem | `expressions_equivalent`: mesma AST, ou uma é subexpressão não trivial da outra |
| `confirmed_by_location.*` | `report.py:69-77` | idem, só hipóteses CONFIRMED | **não exige o tipo esperado** |
| `same_function_other_line` | `report.py:92-98` | bug | falhou na função em outra linha |

O `fp` e a `precision` desses blocos contam hipóteses em outras expressões das **funções rotuladas**. Como não existe função sem bug na entrada, isso não é falso positivo no sentido usual. **Não use essas precisões no artigo.**

### 3.2 Cálculo sobre a rodada de 16/11 (106 resultados, 105 hipóteses únicas, 47 bugs) [F]

**Por hipótese (105 únicas):**
- na função rotulada: 105;
- casa com `expression` pelo comparador: 29;
- casa só com `crash_expressions`: 11;
- casa com algum dos dois: 40;
- texto idêntico: 8.

**Por bug (47):**

| Critério | Bugs | Observação |
|---|---:|---|
| arquivo | 47 | por construção |
| função | 47 | por construção |
| expressão, texto idêntico | 8 | igual ao relatório |
| expressão, comparador AST (`expression` ou `crash`) | 36 | igual ao relatório |
| replay com o tipo esperado na função (regra oficial) | 13 | |
| idem, com a linha da exceção na expressão rotulada ou de estouro | **11** | perdem piouart_6 e pycomm3_331 |
| idem, com a hipótese contada também casando com o rótulo (comparador) | **9** | perdem também gps_126 e opcua_671, por limite do comparador (seção 4.3) |
| CONFIRMED + tipo esperado (regra oficial) | 8 | |
| idem, com a linha na expressão rotulada ou de estouro | **8** | todos |
| idem, casando com o campo `expression` (sem `crash`) | 5 | blinka_434, dronekit_890, paho_118, pymodbus_2921, simpleio_43 |
| CONFIRMED com qualquer tipo, hipótese casando com o rótulo (`confirmed_by_location.expression_equivalent`) | 8 | **conjunto diferente**: entra pymodbus_2980, sai gps_126 |
| bugs com `expected_type = struct.error` que podem ser reproduzidos | 0 de 5 | seção 4.1 |

**Os 13 "apontados e reproduzidos", um a um** (hipóteses que contaram; linha convertida para o arquivo com bug):

| Bug | Hipótese | Veredito | Status do replay | Casa com o rótulo? | Linha da exceção | Rótulo (linha) |
|---|---|---|---|---|---|---|
| blinka_434 | 560d455ab903 | CONFIRMED | reproduced | sim (`expression`) | 52 | 52 |
| cantools_804 | 792b86d01c11 | UNVALIDATED | reproduced | sim | 868 | 863, 868 |
| dronekit_890 | ac4865dcbf0f | CONFIRMED | reproduced | sim | 1778 | 1778 |
| gpiozero_716 | e99a365d8f91 | CONFIRMED | reproduced | sim (`crash`) | 146 | causa 121, estouro 146 |
| gpiozero_716 | e8954a64c90b | NOT_CONFIRMED | other_failure | não | 146 | idem |
| gps_126 | 0c8ade1016ba | CONFIRMED | reproduced | não pelo comparador (texto com `;`) | 494 | 494 |
| gps_126 | 421263434a1b | OTHER_FAILURE | other_failure | não | 494 | 494 |
| gps_60 | bf5f36c91db4 | CONFIRMED | reproduced | sim (`crash`) | 112 | causa 251, estouro 112 |
| mavproxy_1447 | ecceb7eeba0f | UNVALIDATED | reproduced | sim | 54 | 54 |
| mavproxy_1447 | 3fecf2adbc3d | OTHER_FAILURE | other_failure | não (reparo moveu a hipótese) | 54 | 54 |
| opcua_671 | 94bac9a0c7d4 | BOUND_INCONCLUSIVE | reproduced | não (rótulo é só atributo) | 528 | 528 |
| paho_118 | c8c50a884b69 | CONFIRMED | reproduced | sim | 2637 | 2637 |
| paho_118 | 0f95c2c2c63f | ESBMC_TIMEOUT | other_failure | não | 2637 | 2637 |
| piouart_6 | 3e119c7e2e18 | BOUND_INCONCLUSIVE | other_failure | não | **186** | causa 187, estouro 189 |
| pycomm3_331 | bfbf92e3562e | NOT_CONFIRMED | other_failure | sim | **39** | 36-38 |
| pycomm3_331 | 4dd47c4de871 | NOT_CONFIRMED | other_failure | sim | **39** | 36-38 |
| pymodbus_2921 | 8432febfbe95 | CONFIRMED | reproduced | sim | 24 | 24 |
| simpleio_43 | e5d6b90703b8 | CONFIRMED | reproduced | sim | 241 | 241 |

**Mensagens que mostram outra falha com o mesmo tipo [F]:**
- piouart_6: `memoryview: a bytes-like object is required, not 'list'`, levantada fora da função alvo (`raised_at` 71, `target_range` 89-100), dentro de `self.readinto(buf)`. O defeito do patch é `n` ser None em `n < len(buf)`.
- pycomm3_331: `bytes must be in range(0, 256)`, em `return bytes(chain.from_iterable(pairs))`. O defeito corrigido é o tamanho ímpar, que quebra o desempacotamento `x1, x2`.

Contando só reproduções da falha descrita pelo patch, ficam 11 de 13 **[I]**.

**Confirmação ESBMC e replay na mesma linha [F]:** nas 13 hipóteses CONFIRMED, a linha da violação `uncaught exception` no log do ESBMC é igual à linha do replay, com duas exceções:
- blinka_434: a violação fica no ajudante `_esbmc_none_attribute`, chamado na linha da suspeita;
- gps_127: o último log só tem `unwinding assertion`, e o CONFIRMED veio do caminho "timeout após contraexemplo parcial" (`loop.py:313-320`). Esse bug não entra nos 8, porque o tipo é ValueError e o esperado é IndexError.

**CONFIRMED com tipo diferente do esperado [F]:** 5 de 13 hipóteses:

| Bug | Tipo do replay | Esperado | Hipótese |
|---|---|---|---|
| gps_127 | ValueError | IndexError | `degrees = int(raw[0]) // 100 * 1000000` |
| mavproxy_1032 | ZeroDivisionError | AttributeError | `1.0 / self.FakeGPS_settings.rate` |
| mavproxy_881 | KeyError | TypeError | `self.read_gap_times[g]` |
| pymodbus_1738 | IndexError | struct.error | `count = int(buffer[7])` |
| pymodbus_2980 | IndexError | struct.error | `byte_count = int(data[0])`, a própria expressão rotulada |

### 3.3 Rodada de 11/11 (116 resultados, 114 únicas), com a regra atual [F]

| Critério | Bugs |
|---|---:|
| expressão, comparador | 37 |
| expressão, texto idêntico | 6 |
| apontado e reproduzido | 13 |
| idem, linha na expressão rotulada ou de estouro | 10 |
| idem, hipótese casando com o rótulo e na linha | 9 |
| confirmado (tipo esperado) | 9 |
| idem, na linha e casando com o rótulo | 8 |
| CONFIRMED com tipo diferente do esperado | 6 de 15 hipóteses |

Casos novos de 11/11:
- **mavproxy_1572** (`0ab9fc7c348b`) conta como confirmado, mas é outro defeito. O rótulo é `self.master` ser None. A hipótese é `payload.extend(...)` com `'bytes' object has no attribute 'extend'`, porque o harness fez `pack()` devolver `bytes`. O tipo AttributeError coincide por acaso.
- **ros2cli_646** (`20b260c9b659`) conta como reproduzido com `'_Obj_args' object has no attribute 'filter'`. É um objeto falso do harness sem o atributo, ou seja, um artefato.

Também em 11/11, pycomm3_331 é contado pela mesma falha `bytes must be in range`.

### 3.4 Denominadores

- **Bugs (47)**: unidade de `by_function` e dos `tp`/`fn`.
- **Hipóteses (106 com duplicata, 105 únicas)**: unidade dos vereditos e do `fp`. A duplicata é `efd0d98e1388`, pyspartn_4, `self._key = bytes.fromhex(key)`, que as duas variantes produziram.
- Cada função recebe exatamente 2 hipóteses (53 funções × 2 variantes = 106) **[F]** (`detection.analyzed_units = 53`, `hypotheses = 106`).
- Teto realista para "reproduzido com o tipo esperado": 42 bugs, por causa dos 5 de struct.error **[F]**.

---

## 4. Problemas de validade das métricas

### 4.1 struct.error é inalcançável [F]

- O replay grava `type(exc).__name__` (`replay_worker.py:250`). `python3 -c "import struct; print(struct.error.__name__)"` imprime `error`. A comparação `replay.exception_type != expected_type` (`v2_evaluator.py:283`) nunca aceita `struct.error`. A docstring de `evaluate_functions` reconhece isso ("A bare error cannot establish struct.error", l.295-296), mas o teto não aparece no relatório.
- Mesmo com o nome corrigido, o harness troca `struct` por uma classe stub. `programs/f330a5b2a35a_a0_replay.py:9-13` mostra `class struct:` com `unpack` devolvendo uma tupla de `nondet_int()`. Assim, `struct.unpack` nunca levanta erro, nem no replay.
- Em 16/11, nenhuma das 106 hipóteses tem `exception_type == 'error'` **[F]**.
- **Efeito:** pymodbus_2980, pymavlink_1259, opcua_1955, pymodbus_1738 e pymodbus_2977 estão no denominador de 47 sem chance de entrar no numerador. O exemplo de `expected_type` citado na própria `REGRA_DE_ACERTO` (`struct.error`) é justamente o tipo que nunca casa.

### 4.2 Reprodução não é localização

A regra `other_failure` dentro da função (`v2_evaluator.py:286-290`) aceita qualquer exceção do mesmo tipo em qualquer linha da função. Em 16/11, 2 dos 13 entram por falhas sem relação com o patch (seção 3.2). Em 11/11, de 2 a 3. **[I]** Para tipos comuns (TypeError, AttributeError, ValueError), coincidir no tipo é fácil, porque o harness tem objetos falsos e stubs que geram essas exceções sozinhos.

### 4.3 O comparador de expressões tem viés conhecido [F]

- **Falso negativo, vários comandos:** `_normalized` devolve None para mais de um comando (`v2_evaluator.py:56-63`). Em 16/11, 4 hipóteses não podem casar com nada, entre elas a confirmada do gps_126. O grounding, por sua vez, aceita a primeira peça (`astutil.py:211-222`). Grounding e avaliação usam regras diferentes para o mesmo texto.
- **Falso negativo, rótulo só referência:** opcua_671 (`app.DiscoveryUrls`) não casa com `for url in app.DiscoveryUrls:`, que é exatamente o comando corrigido.
- **Falso positivo, rótulo longo:** a regra de subexpressão aceita qualquer pedaço não trivial (`v2_evaluator.py:79-85`). Em mavproxy_1032, `e12392747e87` (`int(gps_lat * 10000000.0)`, suspeita de TypeError ou ValueError, replay com ZeroDivisionError em outra linha) "casa" com o `crash_expressions`, que é a chamada `gps_input_send(...)` de 7 linhas.
- **Falso positivo, rótulo vizinho:** ver seção 2.5.

### 4.4 CONFIRMED não depende do gabarito, e o relatório mistura isso

`confirmed_by_location` usa todas as hipóteses CONFIRMED, sem o tipo esperado (`report.py:69-77`). O número 8 que sai dali coincide com o `confirmado_esbmc` por função, mas os conjuntos diferem (seção 3.2). **[I]** Parece concordância entre duas métricas, mas é coincidência de contagem.

### 4.5 O que o ESBMC prova depende de reescritas do pipeline [F]

- `none_guards` insere `raise` explícito. O ESBMC prova que o valor pode ser None naquele ponto do harness, e o tipo da exceção é decidido pelo pipeline (blinka_434, seção 1.3).
- `cut_after_suspect` corta o resto do bloco no programa do ESBMC (ex.: `programs/f330a5b2a35a_a0.py:62`, com `pass` no lugar do laço com `struct.unpack`).
- `"null pointer"` vira {AttributeError, TypeError} e `"array bounds"` vira IndexError (`outcome.py:79-82`). No pymodbus_2921, as primeiras violações vieram do modelo `int.from_bytes` do ESBMC (`/esbmc-vfs/python/models/int.py` l.28, `array bounds violated`), em `data[0:2]`, que no CPython é seguro. O `uncaught exception: IndexError` na linha da suspeita também aparece (log `programs/8432febfbe95_a0/.../8432febfbe95_a0_3ece8a4cf0_direct.log:135-170` e `:405-407`). Como as exceções são comparadas como conjunto, a confirmação vale. O conjunto, porém, inclui um aviso que **[I]** parece falso alarme do modelo.
- CONFIRMED pode sair de um contraexemplo parcial depois de timeout (`loop.py:313-320`, gps_127).

### 4.6 O domínio das entradas é pequeno [F]

`bytes` só vale `b"ab"` ou `b""` (`render.py:146-147`). Listas e dicionários têm no máximo 2 elementos não determinísticos (`render.py:152-154`). **[I]** Os bugs de buffer confirmados (pymodbus_2921, gps_60, paho_118) são do tipo "entrada vazia ou curta". Bugs que pedem um buffer de 7 ou mais bytes, ou um `byte_count` incoerente (os de struct.error), ficam fora do alcance do harness, não da LLM.

### 4.7 A localização do confirmado nem sempre é o caminho real [F]

- gps_60: a hipótese confirmada está em `_parse_talker`, que o patch não toca. O patch põe o guarda em `update` (`if len(data_type) < 5: return False`). O harness chama `_parse_talker` direto com `data_type` vazio. **[I]** Isso prova a falha da função isolada, não que `update` chegue lá com essa entrada.
- gpiozero_716: o harness cria o receptor sem `__init__` (`receiver_init_replaced`) e põe `min_temp == max_temp`. O bug real é o construtor aceitar esses valores. **[I]** Aqui a correspondência é boa, porque o patch fecha exatamente esse estado.

---

## 5. Casos auditados (Parte D)

Os trechos são do arquivo com bug do dataset. A condição de disparo está resumida a partir de `trigger_condition`.

**5.1 Acerto inequívoco: simpleio_43, `e5d6b90703b8`, CONFIRMED.**
- Hipótese: `mapped = (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min`; ZeroDivisionError quando `in_min == in_max`.
- Rótulo: a mesma linha (`changed_line`, linha 241), ZeroDivisionError.
- Replay: `float division by zero` na linha 241. ESBMC: violação na mesma linha do programa (linha 9, `map_range`).
- Por que é inequívoco: a expressão, a linha, o tipo e a mensagem batem, e a linha é a que o patch reescreve.

**5.2 Acerto parcial: gpiozero_716, `e99a365d8f91`, CONFIRMED.**
- Hipótese: `(self.temperature - self.min_temp) / temp_range` em `CPUTemperature.value`; `temp_range` zero quando `max_temp == min_temp`.
- Rótulo: causa `self.min_temp = min_temp` no `__init__` (vizinha do guarda inserido, linha 121); estouro em `crash_expressions` (linha 146).
- Por que é parcial: a hipótese casa com o ponto de estouro, não com o rótulo principal, e está numa função que o patch não alterou. O pipeline acertou o sintoma, e a causa (o construtor sem validação) ficou implícita no harness.

**5.3 Expressão vizinha: mavproxy_1032.**
- Código (linhas 72-75): `def idle_task(self):` / `now = time.time()` / `if now - self.last_send < 1.0 / self.FakeGPS_settings.rate:`.
- Rótulo: `now = time.time()` (`statement_after_insertion`), AttributeError; o patch insere `if self.master is None: return` antes dela.
- Hipóteses:
  - `ffe06b599b73` suspeita de `1.0 / self.FakeGPS_settings.rate` (rate = 0), CONFIRMED com ZeroDivisionError;
  - `e12392747e87` suspeita de `int(gps_lat * 10000000.0)` e "casa" com o `crash_expressions` por subexpressão.
- Por que importa: a primeira é uma confirmação real **no harness** de outra falha, e por isso não conta pelo tipo. A segunda conta como acerto de expressão sem ter relação com `self.master` ser None.

**5.4 Gabarito ambíguo: pymodbus_2980, `f330a5b2a35a`, CONFIRMED com IndexError.**
- Código (função recortada, linhas 4-7): `self.records = []` / `byte_count = int(data[0])` / `for count in range(1, byte_count, 7):` / `decoded = struct.unpack(">BHHH", data[count : count + 7])`.
- Hipótese: `byte_count = int(data[0])`, IndexError com `data = b""`.
- Rótulo: a mesma expressão (`changed_line`), `expected_type = struct.error`, estouro em `struct.unpack(...)`.
- Por que é ambíguo: a hipótese está na expressão rotulada, mas descreve outra falha. O patch mantém `int(data[0])`, então o buffer vazio **[I]** continua quebrando depois da correção. O tipo esperado não pode ser reproduzido (seção 4.1). Entra no "8 por expressão" e fica fora do "8 por função".

**5.5 Erro de grounding com reparo que moveu a hipótese: mavproxy_1447, `3fecf2adbc3d`, OTHER_FAILURE.**
- Código (linhas 54-61): `print("Flight battery:   %u%%" % self.battery_level[0])` e, no laço, um `%` com `self.per_cell[id]`, `self.numcells(id)`, `self.current_battery[id]` e `self.battery_level[id]`.
- Hipótese original: `self.per_cell[id], self.current_battery[id], self.battery_level[id]`. Não existe como nó único, e por isso deu GROUNDING_FAILED na tentativa 0.
- Reparo: trocou a expressão por `self.current_battery[id]`. Replay: `KeyError '0'` na linha 54, que é a do rótulo, mas não a da hipótese reparada (`other_failure`).
- Rótulo: `self.battery_level[0]`, linha 54, KeyError.
- Por que importa: o bug entra nos 13 por esta hipótese **e** pela `ecceb7eeba0f`, que acertou de fato (`reproduced`). Sozinha, a `3fecf2adbc3d` seria um acerto concedido pela regra frouxa a uma hipótese movida pelo reparo.

**5.6 Reprodução sem correspondência com a localização: piouart_6, `3e119c7e2e18`, BOUND_INCONCLUSIVE, contado como reproduzido.**
- Código (linhas 182-189): `if self.bits > 8:` / `buf = array.array(n)` / `else:` / `buf = bytearray(n)` / `n = self.readinto(buf)` / `if n == 0:` / `return None` / `if n < len(buf):`.
- Hipótese: `buf = array.array(n)`, TypeError porque `n` não é typecode.
- Rótulo: `n == 0` (linha 187), estouro `n < len(buf)` (189), TypeError com `n` None.
- Replay: TypeError `memoryview: a bytes-like object is required, not 'list'`, levantado fora da função alvo, dentro de `readinto`, na linha 186.
- Por que importa: a hipótese, a linha e a causa são outras. Só o nome da exceção coincide.

**5.7 Confirmação de outro defeito com o tipo certo (11/11): mavproxy_1572, `0ab9fc7c348b`, CONFIRMED.**
- Hipótese: `payload.extend(bytearray([0] * (HDR_Len + MAX_Payload - plen)))`, AttributeError se `pack()` devolver `bytes`.
- Rótulo: `self.master.mav.file_transfer_protocol_send(...)` (linha 190), AttributeError com `self.master` None.
- Replay: `'bytes' object has no attribute 'extend'`.
- Por que importa: pela regra atual, esse bug conta como confirmado em 11/11. **[I]** É coincidência de tipo, e a falha depende de um tipo escolhido para o stub.

---

## 6. Correções possíveis só com reanálise (sem LLM e sem nova rodada)

Tudo abaixo usa os JSON, os programas salvos e os logs já gravados. Nenhum item precisa de chamada paga.

1. **Relatar o teto de 42** e mostrar os 5 de struct.error à parte, ou tirá-los do denominador do nível "reproduzido", com a justificativa. Decisão sua.
2. **Acrescentar um nível estrito, calculado só como apoio:** hipótese na expressão rotulada ou de estouro, **e** linha do replay nessas linhas, **e** tipo esperado. Em 16/11: 9 reproduzidos e 8 confirmados, ou 11 e 8 se o comparador for corrigido (item 3). Em 11/11: 9 e 8.
3. **Corrigir o comparador** para tratar `;` como o grounding trata (aceitar se alguma peça casar) e para aceitar cabeçalho `for`/`if` cujo iterável ou condição seja o rótulo. Depois, recalcular as duas rodadas. É código de avaliação, não de detecção, e não muda vereditos.
4. **Separar `other_failure`** quando `raised_at` estiver fora do `target_range` (pega piouart_6) e listar as mensagens dos 13 para leitura humana (pega pycomm3_331). O avaliador já guarda `message` e `raised_at`.
5. **Mostrar os dois "8" com seus conjuntos** e a tabela dos CONFIRMED com tipo diferente.
6. **Marcar as hipóteses movidas pelo reparo** (`healing[*].hypothesis_after`) e mostrar se contaram.
7. **Revisar à mão os 13 rótulos vizinhos** e dizer, para cada um, se a expressão rotulada é causa, sintoma ou só vizinha. O campo `crash_expressions` já cobre 10.
8. **Conferir `source` contra `_patch_touch`** nos 47, com os arquivos `arquivo_com_bug` e `arquivo_corrigido`, sem rede.
9. **[I]** `scripts/patch_rule.py` já roda a hipótese contra o arquivo corrigido reaproveitando o spec salvo, sem LLM, mas **executa o ESBMC**. Isso permitiria ver, por exemplo, se o IndexError do pymodbus_2980 continua depois do patch. Rodar ou não é decisão sua.

## 7. Melhorias que exigem novos experimentos

1. **Negativos:** rodar a detecção no arquivo inteiro, ou com funções não rotuladas misturadas, e nas versões corrigidas. Sem isso não há precisão.
2. **Modelar `struct.unpack`** no harness, com erro quando o tamanho não bate, e gravar o nome qualificado da exceção (`module.qualname`) no replay.
3. **Ampliar o domínio de `bytes`** além de `b"ab"`/`b""` e medir quantos bugs entram.
4. **Exigir alcance pelo chamador real** quando o rótulo tem duas funções (gps_60, gpiozero_716, mavproxy_881): harness que entra pela função do patch.
5. **Reexecutar o contraexemplo exato do ESBMC** no CPython, em vez de busca própria, e relatar as duas coisas.
6. **Segundo rotulador independente** para `expression`, `crash_expressions` e `expected_type`, com concordância medida, e execução da versão com bug para confirmar o tipo.
7. **Separar o efeito das reescritas** (`none_guards`, `cut_after_suspect`): rodar parte dos casos com e sem elas.
8. **Várias rodadas da mesma configuração** congelada, para medir a variação (já apontado na auditoria do pipeline).

## 8. Afirmações defensáveis

### Para o artigo de CPS (entrega 30/11/2026)

- **[F]** "Em 47 bugs reais de projetos Python ciber-físicos, usados como conjunto de desenvolvimento, o pipeline produziu para 8 bugs um harness em que o ESBMC e a execução em CPython concordam na exceção esperada. Nos 8, a falha ocorre na linha rotulada como causa ou como ponto de estouro." Esta frase está apoiada pelos artefatos de 16/11.
- **[F]** "Desses 8, 5 coincidem com a expressão alterada pelo patch, 2 com o ponto de estouro em outra função e 1 com a linha rotulada, em forma textual diferente."
- **[F]** "A confirmação vale para o harness. O pipeline substitui dependências por stubs não determinísticos, insere guardas explícitos para valores None e corta o caminho depois da expressão suspeita."
- **[F]** "5 dos 47 bugs (struct.error) não podiam ser reproduzidos na configuração usada."
- **[F]** "13 bugs tiveram a exceção esperada reproduzida no harness; em 2 deles, a exceção veio de outra causa." Diga isso, ou use 11 com o critério estrito.
- Pode descrever o grounding como "checagem de que a expressão citada pela LLM existe na função", nunca como "localização do defeito".

### Para o mestrado

- Mesmas frases, mais a matriz da seção 3 com os dois critérios (oficial e estrito) lado a lado.
- **Não sustentado com os dados atuais:**
  - que o pipeline "localiza" bugs: sem negativos e com o recorte só das funções rotuladas;
  - que CONFIRMED implica o defeito do patch: 5 de 13 confirmados são de outro tipo, e em 11/11 há um de outro defeito com o mesmo tipo;
  - qualquer precisão ou F1 tirado de `detection_by_location`.

---

### Nota sobre o uso de IA

Este documento foi escrito por IA (Claude Code), que leu o código e os artefatos e fez as contagens por script de leitura. As interpretações marcadas como [I] e [H] são da IA e precisam da sua conferência. Não houve revisão humana antes desta entrega.
