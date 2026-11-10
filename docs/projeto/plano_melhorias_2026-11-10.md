# Plano de melhorias do pipeline antes do scan (10/11/2026)

Proposta da IA. A Fernanda escolhe o que entra e o que fica para depois. Baseado na rodada completa dos 47 de
09/11 (`artifacts/pgene601/rodada-final-2026-11-09/`): 9 de 47 confirmados pela expressão e 14 pela função,
os mesmos números de 08/11. Itens 2 a 4 implementados; itens 1, 5 e 6 ficaram em diagnóstico.

## Regras do plano

- Um item por vez, com teste que falha antes e passa depois.
- Cada item é medido só nos bugs que ele deveria mover (subconjunto), antes de qualquer rodada completa.
- Uma única rodada completa dos 47 no fim, e depois o scan do pymodbus. O scan não começa antes.
- Qualquer item que mude como o veredito é decidido (itens 1 e 2) é registrado como mudança de critério e declarado
  no artigo. A decisão de aceitar o critério novo é da Fernanda e do orientador.
- Sem commit sem pedido dela.

## Onde os 47 pararam (09/11)

| Parada | Bugs | Causa |
|---|---:|---|
| CONFIRMED | 9 | |
| LLM_ONLY | 16 | o ESBMC recusa o harness |
| UNVALIDATED | 3 (6 vistos nos dados) | o ESBMC acha erro, o replay não confirma |
| NOT_CONFIRMED, ESBMC_MISSED, TIMEOUT, ERROR, OTHER, SPEC_FAILED | 9 | |
| Sem hipótese certa | 10 | detecção |

## Itens, em ordem sugerida

### 1. UnboundLocalError reproduzido, mas o ESBMC diz AttributeError (cantools_804)
- Fato: esperado `UnboundLocalError`. O replay reproduziu `UnboundLocalError` na linha 73. O ESBMC deu `AttributeError`.
  O veredito ficou UNVALIDATED só porque `replay.exception_type in reading.exceptions` (`verify/outcome.py:115`) exige o
  mesmo nome.
- Passo 0 (ler antes de mexer): ver a mensagem exata do ESBMC nesse caso e se `AttributeError` é como ele modela nome
  não ligado. Se for acaso, não implementar.
- Se for implementar: equivalência estreita, só quando o replay reproduz `UnboundLocalError` dentro do intervalo do
  alvo (`target_range`) e o ESBMC aponta o mesmo ponto. Nunca uma equivalência geral de `AttributeError`.
- Teste: unitário em `tests/test_verify_outcome*.py` (ou o arquivo que já cobre `final_verdict`) com os dois lados; e um
  caso negativo (`AttributeError` comum continua UNVALIDATED).
- Risco: afrouxar o critério. Declarar no artigo.
- Medir: cantools_804.

**Passo 0 (09/11, verificado nesta execução):** causa confirmada para `UNVALIDATED`, mas a equivalência estreita proposta
não se aplica a este contraexemplo. O replay reproduz `UnboundLocalError` em `if signals:` (linha 73, dentro do
intervalo 59–76). Rodei o harness salvo, com o ESBMC `b76980aaa0`: ele acusa `AttributeError` na linha 63,
em `for message in database.messages`, antes do ponto reproduzido pelo CPython. Como os pontos não coincidem,
não alterei o veredito nem acrescentei a equivalência. O teste desejado para essa mudança não foi criado porque
nenhuma mudança de critério foi feita. A suíte completa terminou em 8m32s: 1.643 aprovados, 1 ignorado e 13
falhas. São as mesmas falhas da linha de base: 12 em `test_verify_auto_lessons` porque o caderno já tem lições,
e uma em `test_flags_reach_the_arm_and_default_stays_on` porque o cache tenta gravar fora do espaço permitido.

### 2. Replay recusa harness que importa `os` (pyspartn_4, mavproxy_741)
- Fato: `replay.status = unavailable`, motivo `not executed on host: imports os`
  (`verify/sandbox.py:52`, `host_replay_problem`). O ESBMC achou `AttributeError`/`TypeError` nos dois.
- Passo 0: ver por que o `os` aparece no código de replay (import real do arquivo original) e o que o código usa dele.
- Opção: rodar o replay com um módulo `os` falso (só `path`, `environ`, `getenv`), no mesmo isolamento de hoje
  (`unshare --user --net`, limites de processo), sem liberar `os` de verdade. Segurança primeiro: nada que escreva,
  apague ou execute.
- Teste: `tests/test_sandbox*.py` ou o que cobre `host_replay_problem`: harness com `os.path.join` roda; `os.system`,
  `os.remove` continuam recusados.
- Medir: pyspartn_4, mavproxy_741 (e mavproxy_989).

**Passo 0 e implementação:** confirmados nos replays salvos: `pyspartn_4` usa `from os import getenv`; `mavproxy_741`
usa `os.path.getsize`. O sandbox recusava ambos antes de iniciar o replay. O worker agora fornece `os` falso, com
`getenv`, `environ` vazio e somente funções de caminho de leitura; `environ` não aceita escrita. O filtro ainda recusa
`os.system`, `os.remove`, imports desses membros e mutação de `os.environ`. O isolamento de rede e os limites do
processo não mudaram. Teste focado: 7 passaram, incluindo o replay com `os.path.join`, `getenv` e `environ`.
**Mudança de critério:** o pipeline passa a aceitar replay como evidência nos harnesses que usam esse subconjunto
seguro de `os`. A ampliação precisa ser descrita no artigo. A suíte completa após esta alteração está pendente.
Após corrigir duas regressões temporárias dos testes de coroutine e atualizar o teste de recusa geral de `import os`,
a suíte completa terminou em 12m16s: 1.650 aprovados, 1 ignorado e as mesmas 13 falhas da linha de base. Os testes
focados finais passaram: 26 de sandbox e replay, mais 1 teste de integração de coroutine com ESBMC.

### 3. Replay não reproduz em 3 casos (pythoncan_225, pyserial_149, dronekit_890)
- Fato corrigido: o motor já replica com os valores do contraexemplo (`verify/loop.py:383`,
  `counterexample_seeds`). Mesmo assim o replay ficou `not_reproduced` em 400 execuções, com `draws: null`.
- Isto é investigação, não conserto. Passo 0 por caso: o contraexemplo do ESBMC tem valores extraídos? O harness do
  ESBMC e o código que o replay roda são o mesmo? O erro do ESBMC pode ser espúrio (modelo do ESBMC difere do CPython)?
- Resultado possível: nada a corrigir (o ESBMC estava errado) e o veredito UNVALIDATED é o honesto.
- Medir: os 3 bugs, um por vez.

**Resultado do Passo 0 e correção confirmada:** em `pythoncan_225`, `__iter__` é gerador. O driver do replay chamava
o método, mas descartava o gerador, então o corpo não executava no CPython. O harness do ESBMC executava o corpo.
O driver do replay agora consome geradores e há teste que falhava antes e passa depois. A execução diagnóstica com o
gerador consumido alcançou uma exceção `IndexError` anterior ao trecho originalmente suspeito; isso ainda não confirma
que o ESBMC e o replay concordam sobre o erro indicado na hipótese.

Em `pyserial_149`, os valores do witness salvos não foram incorporados ao replay: o campo relevante é uma lista
aninhada, que o extrator atual não converte em sementes. Também há um stub de `serial` sombreado por outro nome
gerado. Não consegui confirmar qual dos dois explica a diferença observada, portanto não alterei extração nem
grounding para este caso. Em `dronekit_890`, um reprodutor pequeno com os tipos do harness faz o ESBMC apontar
desreferência nula numa comparação que o CPython executa; a evidência aponta para diferença no modelo do ESBMC,
sem defeito confirmado no pipeline. Não alterei código por esses dois casos. A medição dos três no pipeline fica
pendente com a autora.

O teste de gerador e a suíte completa após o conserto passaram, respectivamente: 1 teste direcionado e
1.651 aprovados, 1 ignorado e 13 falhas. As 13 falhas repetem a linha de base: 12 pelo caderno de reparos já
preenchido e uma pela tentativa de gravar o cache fora do espaço permitido.

### 4. piouart_6: `bytearray(n)` com `n` reatribuído (1 bug)
- Fato: a regra `compat_bytearray` não disparou porque o tipo do `n` não é conhecido onde a regra olha.
  `verify/compat.py` (`_bytearray_edits`, `_operand_kind`).
- Passo 0: confirmar com o arquivo reescrito por que o `n` não é visto como inteiro (parâmetro reatribuído,
  `n = self.readinto(buf)`, ou domínio de tipos vazio).
- Teste: caso em `tests/test_verify_compat.py`.
- Medir: piouart_6 (a hipótese também tem `array.array(n)` no outro ramo, que o ESBMC não suporta: pode continuar
  recusado por isso).

**Passo 0 e correção:** confirmado no código original e na especificação salva. `n` é parâmetro `int`, usado em
`bytearray(n)` antes de `n = self.readinto(buf)`. A análise de tipos descartava o tipo por encontrar reatribuição em
qualquer ponto do método, inclusive depois do uso. Agora ela preserva o tipo antes da primeira atribuição e o remove
nos pontos posteriores. O teste novo falhava antes e verifica a conversão somente no uso anterior à reatribuição.
`ALL_RULES`, a sonda e a capability `compat_bytearray` já existiam no working tree; não criei regra paralela.
Depois de preservar também os casos em que `import`, `match` e definição de função local sobrescrevem o nome,
113 testes focados passaram. A suíte completa terminou com 1.652 aprovados, 1 ignorado e as mesmas 13 falhas da
linha de base (12 pelo caderno de reparos preenchido e uma pela escrita do cache fora do espaço permitido). Não rodei
ESBMC nem medi `piouart_6` no pipeline; o ramo `array.array(n)` continua sem solução e pode impedir o resultado.

### 5. `str %` com valores não constantes (mavproxy_1380, mavproxy_1447)
- Fato: `unsupported: non-constant argument in str % formatting`. A regra `compat_percent_format` só cobre argumento
  constante. A #8672 do ESBMC (fechada) tratava de `%` com subscript e float: conferir se voltou.
- Passo 0: reduzir a um reprodutor e ver se é regressão do ESBMC (então vira issue) ou limite novo.
- Possível contorno no pipeline: quando o `%` está fora da linha suspeita, trocar a mensagem por `nondet_str()`.
  Precisa preservar o comportamento da função.
- Medir: os dois bugs.

**Passo 0:** os reprodutores mínimos confirmam limites atuais do ESBMC, não uma regressão identificada. Para
`mavproxy_1447`, `nondet_int(); "%u" % n` é recusado. Os três harnesses salvos usam argumentos inteiros dinâmicos
em `%u`. Para `mavproxy_1380`, `%f` com variável `float` simples e com subscript foi aceito, mas um
`Optional[float]` continua recusado mesmo dentro do ramo `if x is not None`; o harness usa esse formato para
`terrain_height`. O histórico local do ESBMC mostra suporte parcial a `%.Nf` dinâmico, enquanto as demais conversões
continuam exigindo constantes. Não confirmei regressão nem relação com a #8672. Sem mudança de código e sem issue;
não criei contorno. Os reprodutores mínimos foram `"%u" % nondet_int()` e, para o caso opcional,
`x: Optional[float]` seguido de `if x is not None: "%.1f" % x`. A suíte terminou com 1.652 aprovados,
1 ignorado e as mesmas 13 falhas da linha de base.

### 6. Elemento de contêiner sem classe (opcua_1131, pymavlink_1217, cantools_595)
- Fato: `Cannot resolve attribute '_instances' on Subscript result`. Há uma lição manual aguardando revisão da
  Fernanda; ela não bastou na rodada de 09/11 (pymavlink_1217 foi de TIMEOUT para LLM_ONLY).
- Passo 0: ler a hipótese e o harness de cada um e ver se a classe é gerada com a anotação certa.
- Só atacar o grounding/spec se a leitura mostrar uma causa comum aos três.

**Passo 0 (somente leitura):** não confirmei uma causa comum.

- `opcua_1131`: `_datachanges` e `_events` saem no harness como `dict[int, list[_Opaque]]`, embora o programa acesse
  `SourceTimestamp` e `Time`. A classe `_HistEvent` aparece no harness, mas a lista continua usando `_Opaque`;
  `DataValue` também não aparece no programa final. Uma tentativa com `dict[int, list[DataValue]]` não chegou a
  preservar essa classe no harness. Proposta: garantir que o tipo do elemento nomeado exista como classe e seja usado
  pelo campo da lista; investigar separadamente o conserto do índice fora do limite.
- `pymavlink_1217`: o primeiro spec usa `dict[str, object]`, e o ESBMC não resolve `_instances` no resultado do
  subscript. Uma tentativa com `dict[str, _Msg]` retirou essa recusa, mostrando que o tipo da classe importa. Porém,
  o driver ainda usa `dict[str, _Opaque]`, e outra hipótese sobre o mesmo método continua sem classe. Proposta:
  alinhar o tipo da classe no parâmetro e no objeto criado pelo driver; verificar isso em cada hipótese.
- `cantools_595`: o erro salvo é diferente: não resolve `.attrib.get()` no elemento percorrido. O harness declara
  `ArxmlElement` e `ArxmlAttrib`, e `_get_arxml_children` declara retorno `list[ArxmlElement]`, mas o ESBMC ainda
  recusa o receiver. O parâmetro `node` foi tentado como `object` e `list[object]`. Proposta: conferir o tipo correto
  de `node` e o tipo que atravessa o retorno da função; não há evidência de que seja o mesmo problema dos outros dois.

Não alterei código e não criei teste, pois este item pede só diagnóstico e proposta. A suíte terminou com
1.652 aprovados, 1 ignorado e as mesmas 13 falhas da linha de base.

### 7. Velocidade (4,8 h de verificação na rodada de 09/11, contra 3,6 h)
- Parar o reparo quando a recusa se repete pelo mesmo motivo.
- Orçamento de tempo por hipótese e bound menor antes da escada.
- Paralelismo entre hipóteses (limite: teto de 5 h da assinatura).
- Só depois de os itens 1 a 6 fecharem, e medido contra o número de confirmados.

## Fora do pipeline, em paralelo

- Issues do ESBMC: #10204 a #10208 abertas. Faltam reduzir 79 a 82 (ver `possiveis_problemas/README.md`).
- Correção da #10208 pronta em `~/esbmc-wt/issue-10208`, sem commit.

## Medição

1. Subconjunto: só os bugs de cada item, com `--resume` e a mesma configuração da rodada de 09/11.
2. Se algum item mover o número, rodada completa dos 47 uma vez no fim.
3. Registrar em `docs/experimentos/README.md` com data, commit, comando e resultado, inclusive se não subir.
4. Depois, o scan do pymodbus (`artifacts/scan_pymodbus_2026-11-09/run.sh`) contra os bugs 2921, 2977 e 2980.
