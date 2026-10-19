# Bugs reais de Python ciber-físico (PGENE601)

Quarenta e sete bugs de execução corrigidos em projetos Python que conversam com hardware, barramentos
e protocolos de campo: drones (MAVLink), barramento CAN, diagnóstico automotivo (UDS), Modbus, OPC UA,
MQTT, GNSS (NMEA, RTCM3, SPARTN), CLP, porta serial, GPIO e ROS 2.
É o dataset da disciplina PGENE601 e fica **separado da dissertação**: não entra nos números da V2,
não se mistura com `dataset/bugs_reais/` e não altera nada lá. O formato, porém, é o mesmo da V2,
então o pipeline roda nele sem mudança de código.

## Origem

Cada item vem de um pull request de correção **aceito e integrado** no repositório oficial do
projeto. A versão com bug e a corrigida são arquivos reais do histórico, baixados do GitHub:

- versão corrigida: o commit de merge do PR;
- versão com bug: o primeiro pai desse merge, que é o estado do ramo principal logo antes da correção;
- exceção em três PRs integrados por rebase (python-can#1811, pyserial#820 e micropython-lib#1149):
  ali o pai do merge já é um commit do próprio PR, e a versão com bug passa a ser o commit anterior ao
  primeiro commit do PR.

O campo `provenance.buggy_commit_rule` diz qual das duas regras valeu em cada item.

## Critério de seleção

A montagem teve duas rodadas. Na primeira, os 45 PRs candidatos de
`docs/projeto/cps_candidatos_2026-10-08.md` foram lidos um a um (título, descrição, diff e, quando
faltava o traceback, a issue ligada); a pré-seleção e os 25 descartes, cada um com o motivo, estão em
`docs/projeto/cps_preselecao_2026-10-12.md`, de onde saíram 20 itens. Na segunda, uma busca em 60
repositórios do domínio rendeu os 30 candidatos de `docs/projeto/cps_candidatos_extra_2026-10-12.md`,
todos aprovados, dos quais 27 puderam ser montados (os 3 restantes estão explicados mais abaixo).
Valeram, nas duas rodadas, as mesmas quatro condições:

1. a versão com bug levanta uma exceção nativa do Python, de preferência na própria função;
2. patch pequeno, que aponta sem ambiguidade a linha do defeito;
3. o dado que dispara o bug vem de fora (hardware, arquivo, rede ou configuração);
4. pouca dependência pesada, de modo que um harness consiga isolar a função.

Contaram como bônus as construções que o ESBMC-Python passou a cobrir nas correções recentes
(#8247 a #8258: método em None, aritmética com None, `in` em Optional, `int()` de string,
UnboundLocalError).

## Os 47 itens

`kind` é o `failure_kind` (`local` = `excecao_local`, `modelável` = `excecao_modelavel`); a coluna
de ressalvas resume o campo `ressalva` do gabarito. Os itens 1 a 20 vêm da primeira rodada e os
itens 21 a 47 da segunda, na mesma ordem dos JSON.

| # | id | PR | grupo | função | exceção | kind | ressalva |
|---|---|---|---|---|---|---|---|
| 1 | `cps_pymodbus_2980` | [pymodbus#2980](https://github.com/pymodbus-dev/pymodbus/pull/2980) | decodificação | `ReadFileRecordRequest.decode` | struct.error | modelável | o PR corrige mais duas funções iguais; só esta está rotulada |
| 2 | `cps_pymavlink_1259` | [pymavlink#1259](https://github.com/ArduPilot/pymavlink/pull/1259) | decodificação | `DFReader_binary.init_arrays_fast` | struct.error | modelável | função longa com mmap |
| 3 | `cps_opcua_1131` | [opcua-asyncio#1131](https://github.com/FreeOpcUa/opcua-asyncio/pull/1131) | decodificação | `HistoryDict.read_node_history / read_event_history` | IndexError | local | **async** |
| 4 | `cps_opcua_1955` | [opcua-asyncio#1955](https://github.com/FreeOpcUa/opcua-asyncio/pull/1955) | decodificação | `DataSetWriter.generate_uadp_dataset` | struct.error | modelável | **async**; estoura no serializador, fora da função |
| 5 | `cps_pythoncan_1811` | [python-can#1811](https://github.com/hardbyte/python-can/pull/1811) | logs e arquivos | `ASCReader.__iter__ / _process_fd_can_frame` | ValueError | local | merge por rebase; `__iter__` é gerador |
| 6 | `cps_cantools_595` | [cantools#595](https://github.com/cantools/cantools/pull/595) | logs e arquivos | `SystemLoader._load_comments` | AttributeError | local |  |
| 7 | `cps_cantools_804` | [cantools#804](https://github.com/cantools/cantools/pull/804) | logs e arquivos | `_dump_signals` | UnboundLocalError | local |  |
| 8 | `cps_pythoncan_1599` | [python-can#1599](https://github.com/hardbyte/python-can/pull/1599) | None do dispositivo | `find_available_interfaces` | KeyError | local | subprocess fica fora do harness |
| 9 | `cps_pythoncan_1293` | [python-can#1293](https://github.com/hardbyte/python-can/pull/1293) | None do dispositivo | `IscanError.__init__` | AttributeError | local | atributo inexistente, não None |
| 10 | `cps_pyserial_820` | [pyserial#820](https://github.com/pyserial/pyserial/pull/820) | None do dispositivo | `PosixPollSerial.read` | UnboundLocalError | local | merge por rebase; `select.poll` precisa de stub |
| 11 | `cps_pyserial_149` | [pyserial#149](https://github.com/pyserial/pyserial/pull/149) | None do dispositivo | `FramedPacket.data_received` | TypeError | local |  |
| 12 | `cps_pymavlink_1217` | [pymavlink#1217](https://github.com/ArduPilot/pymavlink/pull/1217) | None do dispositivo | `add_message` | TypeError | local | `getattr` com nome variável |
| 13 | `cps_mavproxy_1032` | [MAVProxy#1032](https://github.com/ArduPilot/MAVProxy/pull/1032) | None do dispositivo | `FakeGPSModule.idle_task` | AttributeError | local |  |
| 14 | `cps_mavproxy_881` | [MAVProxy#881](https://github.com/ArduPilot/MAVProxy/pull/881) | None do dispositivo | `FTPModule.__init__ / check_read_send` | TypeError | local | nasce no `__init__`, estoura em outro método |
| 15 | `cps_dronekit_890` | [dronekit#890](https://github.com/dronekit/dronekit-python/pull/890) | None do dispositivo | `Vehicle.is_armable` | TypeError | local |  |
| 16 | `cps_blinka_434` | [Adafruit_Blinka#434](https://github.com/adafruit/Adafruit_Blinka/pull/434) | None do dispositivo | `PWMOut.deinit` | AttributeError | local | `RPi.GPIO` precisa de stub |
| 17 | `cps_opcua_1826` | [opcua-asyncio#1826](https://github.com/FreeOpcUa/opcua-asyncio/pull/1826) | None do dispositivo | `UaProcessor._process_message` | TypeError | local | **async**; função enorme |
| 18 | `cps_opcua_671` | [opcua-asyncio#671](https://github.com/FreeOpcUa/opcua-asyncio/pull/671) | None do dispositivo | `application_to_strings` | TypeError | local |  |
| 19 | `cps_ros2cli_1112` | [ros2cli#1112](https://github.com/ros2/ros2cli/pull/1112) | robótica e veículos | `get_port` | ValueError | local |  |
| 20 | `cps_ros2cli_1026` | [ros2cli#1026](https://github.com/ros2/ros2cli/pull/1026) | robótica e veículos | `InterfaceFlags.__str__ / NetworkReport.report` | TypeError | modelável | incerto se o ESBMC checa o retorno de `__str__` |
| 21 | `cps_pymodbus_2921` | [pymodbus#2921](https://github.com/pymodbus-dev/pymodbus/pull/2921) | decodificação | `FramerTLS.decode` | IndexError | local |  |
| 22 | `cps_pymodbus_1738` | [pymodbus#1738](https://github.com/pymodbus-dev/pymodbus/pull/1738) | decodificação | `ReadDeviceInformationResponse.calculateRtuFrameSize` | struct.error | modelável | modelo de `struct.unpack` com fatia curta |
| 23 | `cps_pymodbus_2977` | [pymodbus#2977](https://github.com/pymodbus-dev/pymodbus/pull/2977) | decodificação | `WriteMultipleRegistersRequest.decode` | struct.error | modelável | o PR corrige também `ReadWriteMultipleRegistersRequest.decode`, não rotulada |
| 24 | `cps_minimqtt_5` | [Adafruit MiniMQTT#5](https://github.com/adafruit/Adafruit_CircuitPython_MiniMQTT/pull/5) | decodificação | `MQTT.connect` | IndexError | local | só estoura com CONNACK de recusa; socket precisa de stub |
| 25 | `cps_umqtt_1149` | [micropython-lib#1149](https://github.com/micropython/micropython-lib/pull/1149) | decodificação | `MQTTClient.connect` | IndexError | local | merge por rebase; TypeError se o `read` devolver None |
| 26 | `cps_pyrtcm_34` | [pyrtcm#34](https://github.com/semuconsulting/pyrtcm/pull/34) | decodificação | `RTCMMessage.__str__` | KeyError | local | `__str__` percorre `__dict__` |
| 27 | `cps_pycomm3_331` | [pycomm3#331](https://github.com/ottowayi/pycomm3/pull/331) | decodificação | `PCCCStringType._slc_string_swap` | ValueError | local | patch grande; usa `itertools.chain` |
| 28 | `cps_udsoncan_291` | [udsoncan#291](https://github.com/pylessard/python-udsoncan/pull/291) | decodificação | `AsciiCodec.decode` | UnicodeDecodeError | modelável | depende de `bytes.decode` levantar erro no ESBMC |
| 29 | `cps_udsoncan_198` | [udsoncan#198](https://github.com/pylessard/python-udsoncan/pull/198) | decodificação | `Client.send_request` | UnboundLocalError | local | função enorme |
| 30 | `cps_gps_127` | [Adafruit GPS#127](https://github.com/adafruit/Adafruit_CircuitPython_GPS/pull/127) | decodificação | `_parse_degrees` | IndexError | local | patch grande (cria helper); a versão com bug já traz GPS#126 |
| 31 | `cps_gps_126` | [Adafruit GPS#126](https://github.com/adafruit/Adafruit_CircuitPython_GPS/pull/126) | decodificação | `GPS._update_timestamp_utc` | ValueError | local | `time.struct_time` precisa de stub |
| 32 | `cps_gps_60` | [Adafruit GPS#60](https://github.com/adafruit/Adafruit_CircuitPython_GPS/pull/60) | decodificação | `GPS.update / _parse_talker` | IndexError | local | estoura em `_parse_talker`, chamada por `update` |
| 33 | `cps_pythoncan_713` | [python-can#713](https://github.com/hardbyte/python-can/pull/713) | logs e arquivos | `CanutilsLogReader.__iter__` | UnboundLocalError | local | `__iter__` é gerador; correção longe da linha que estoura |
| 34 | `cps_pythoncan_225` | [python-can#225](https://github.com/hardbyte/python-can/pull/225) | logs e arquivos | `ASCReader.__iter__` | ValueError | local | `__iter__` é gerador; o PR mexe também em `ASCWriter.log_event` |
| 35 | `cps_pymavlink_1058` | [pymavlink#1058](https://github.com/ArduPilot/pymavlink/pull/1058) | logs e arquivos | `DFReader_binary.init_arrays_fast` | KeyError | local | mesma função de `cps_pymavlink_1259`, outro bug; patch quase todo reindentação |
| 36 | `cps_mavproxy_989` | [MAVProxy#989](https://github.com/ArduPilot/MAVProxy/pull/989) | logs e arquivos | `LogModule.log_status` | ZeroDivisionError | local | mesma função de `cps_mavproxy_741`, outra versão |
| 37 | `cps_mavproxy_741` | [MAVProxy#741](https://github.com/ArduPilot/MAVProxy/pull/741) | logs e arquivos | `LogModule.log_status` | ValueError | local | mesma função de `cps_mavproxy_989`, outra versão |
| 38 | `cps_piouart_6` | [Adafruit PIO_UART#6](https://github.com/adafruit/Adafruit_CircuitPython_PIO_UART/pull/6) | None do dispositivo | `UART.read` | TypeError | local | `readinto` vira stub Optional |
| 39 | `cps_mavproxy_1572` | [MAVProxy#1572](https://github.com/ArduPilot/MAVProxy/pull/1572) | None do dispositivo | `FTPModule.send` | AttributeError | local | mesmo padrão de `cps_mavproxy_1032` |
| 40 | `cps_mavproxy_1447` | [MAVProxy#1447](https://github.com/ArduPilot/MAVProxy/pull/1447) | None do dispositivo | `BatteryModule.cmd_bat` | KeyError | local |  |
| 41 | `cps_gpiozero_716` | [gpiozero#716](https://github.com/gpiozero/gpiozero/pull/716) | None do dispositivo | `CPUTemperature.__init__ / value` | ZeroDivisionError | local | corrigido no `__init__`, estoura na property |
| 42 | `cps_simpleio_43` | [Adafruit SimpleIO#43](https://github.com/adafruit/Adafruit_CircuitPython_SimpleIO/pull/43) | None do dispositivo | `map_range` | ZeroDivisionError | local |  |
| 43 | `cps_pyspartn_4` | [pyspartn#4](https://github.com/semuconsulting/pyspartn/pull/4) | None do dispositivo | `SPARTNMessage.__init__` | TypeError | modelável | depende do modelo de `bytes.fromhex`; o PR mexe também em outro arquivo |
| 44 | `cps_mavproxy_1380` | [MAVProxy#1380](https://github.com/ArduPilot/MAVProxy/pull/1380) | robótica e veículos | `MPSlipMapPanel.click_position_text` | TypeError | local | arquivo de interface wx |
| 45 | `cps_ros2cli_370` | [ros2cli#370](https://github.com/ros2/ros2cli/pull/370) | robótica e veículos | `_check_network_config_helper` | AttributeError | local | `ifcfg.interfaces()` precisa de stub |
| 46 | `cps_ros2cli_646` | [ros2cli#646](https://github.com/ros2/ros2cli/pull/646) | robótica e veículos | `ListVerb.main` | AttributeError | local | `main` usa rclpy |
| 47 | `cps_paho_118` | [paho-mqtt#118](https://github.com/eclipse-paho/paho.mqtt.python/pull/118) | outros | `Client._host_matches_cert` | IndexError | local |  |

### Contagem por grupo

| grupo | 1ª rodada | 2ª rodada | total |
|---|---|---|---|
| decodificação de pacote ou mensagem | 4 | 12 | 16 |
| logs e arquivos | 3 | 5 | 8 |
| None do dispositivo ou da configuração | 11 | 6 | 17 |
| robótica e veículos (inclui ROS 2) | 2 | 3 | 5 |
| outros | 0 | 1 | 1 |
| total | 20 | 27 | 47 |

Resumo: 39 `excecao_local` e 8 `excecao_modelavel`, todos com destino esperado no ESBMC pela
triagem. Por categoria, são 14 `none_misuse`, 13 `out_of_bounds`, 6 `invalid_precondition`,
5 `type_mismatch`, 5 `variable_misuse`, 3 `division_by_zero` e 1 `integer_overflow`.

### Ressalvas que pesam no harness

- Itens **async** (`cps_opcua_1131`, `cps_opcua_1955`, `cps_opcua_1826`): contam na métrica de
  detecção, mas o motor `verify` só aterra funções síncronas, então a confirmação pelo ESBMC exige
  recortar à mão o corpo síncrono.
- Patch grande em relação ao bug aparece em `cps_pycomm3_331`, `cps_gps_127` e `cps_pymavlink_1058`
  (este quase todo reindentação). Em `cps_pymodbus_2980` e `cps_pymodbus_2977` o PR corrige o mesmo
  padrão em outras funções, e só uma ficou rotulada.
- Quando o bug atravessa duas funções, `function` traz as duas separadas por ` / `
  (`cps_opcua_1131`, `cps_pythoncan_1811`, `cps_mavproxy_881`, `cps_ros2cli_1026`, `cps_gps_60`,
  `cps_gpiozero_716`).
- Dependem de modelo de biblioteca no ESBMC: `struct.unpack` em quatro itens de decodificação,
  `bytes.decode` em `cps_udsoncan_291` e `bytes.fromhex` em `cps_pyspartn_4`.
- Dois pares repetem função: `cps_mavproxy_989` com `cps_mavproxy_741` (`log_status`, em versões
  diferentes) e `cps_pymavlink_1058` com `cps_pymavlink_1259` (`init_arrays_fast`, bugs diferentes).
- Em `cps_gps_127`, a versão com bug é o merge de GPS#126, porque esse é o primeiro pai; a correção
  de `cps_gps_126` já está presente ali.

### Aprovados que ficaram de fora

Três dos 30 aprovados na segunda rodada não entraram, porque montá-los exigiria alterar o código
original:

| PR | motivo |
|---|---|
| [scapy#5089](https://github.com/secdev/scapy/pull/5089) | o bug mora em lambdas dentro de `fields_desc`, no corpo da classe `MQTTPublish`; não existe função a rotular, e criar uma `f(pkt)` seria inventar código |
| [dronekit#431](https://github.com/dronekit/dronekit-python/pull/431) | o arquivo no commit com bug usa `await` como nome de variável, o que o Python 3.7 em diante recusa; nem o `ast.parse` do pipeline nem o frontend do ESBMC leem o arquivo |
| [dronekit#611](https://github.com/dronekit/dronekit-python/pull/611) | mesmo problema de `await` como variável no `dronekit/__init__.py` daquela época |

## Arquivos

Mesma organização de `dataset/bugs_reais/`:

| Pasta ou arquivo | Conteúdo |
|---|---|
| `funcao_com_bug/` | só a função com bug (o que a LLM lê); método aparece dentro de um cabeçalho `class` vazio |
| `arquivo_com_bug/` | o arquivo completo no commit com bug (o pipeline monta o harness a partir dele) |
| `arquivo_corrigido/` | o arquivo completo no commit de merge (controle de confirmação falsa) |
| `patches/` | diff do arquivo-fonte entre as duas versões |
| `ground_truths.json`, `manifest.json` | gabarito; o manifesto aponta `detection_file` para `funcao_com_bug/` |
| `manifest_full.json` | igual ao manifesto, com `detection_file` apontando para `arquivo_com_bug/` |

No gabarito, `expression` é onde o bug nasce: a linha que o patch reescreve ou, quando o patch só
insere uma guarda, a instrução vizinha à inserção (`label_sources.expression` diz qual). Já
`crash_expressions` lista onde a exceção estoura quando é outra linha. Em relação aos itens `bip_*`,
três campos são novos: `expected_type` (a exceção da versão com bug), `ressalva` (o que dificulta o
harness) e `provenance.pr_url`. Quando o bug atravessa duas funções, `function` lista as duas
separadas por ` / `, como já se faz na V2.

## Como foi montado e conferido

O script `scripts/build_disciplina_pgene601.py` baixa as duas versões de cada arquivo, recorta a função,
gera o patch e escreve os três JSON; rodá-lo de novo refaz a pasta inteira. Antes de gravar cada
item ele confere três coisas e aborta se alguma falhar:

- a `expression` existe, AST-equivalente, na função da versão com bug, e também no recorte;
- cada `crash_expressions` existe na versão com bug;
- o patch reescreve a linha da `expression` ou insere código colado nela.

Depois o gabarito foi carregado com o próprio código do pipeline, sem LLM e sem ESBMC: a auditoria
de dataset (`audit_dataset`) achou as 47 expressões na função rotulada, sem nenhum problema, e a
avaliação de detecção (`evaluate_detection`) alimentada com as hipóteses do próprio gabarito
(`_load_v2_oracle_candidates`) deu 47 de 47 por localização e por expressão. Na segunda rodada, um
diff dos três JSON e das quatro pastas antes e depois confirmou que os 20 itens da primeira ficaram
idênticos.

## Como rodar o pipeline

No formato de `docs/experimentos/README.md`, trocando só a entrada, o gabarito e as fontes:

```
PYTHONPATH=src .venv/bin/python src/main.py --mode hybrid --v2-stage end-to-end \
  --input dataset/disciplina_pgene601/funcao_com_bug --ground-truth dataset/disciplina_pgene601/ground_truths.json \
  --verification-sources dataset/disciplina_pgene601/arquivo_com_bug \
  --backend claude_cli --model claude-sonnet-5-5 --synth-backend claude_cli --synth-model claude-sonnet-5-5 \
  --bound 5 --timeout 180 --output-dir artifacts/disciplina_pgene601/<pasta>
```

A rodada chama a LLM. Para medir só a síntese de harness a partir das hipóteses do gabarito, sem a
etapa de detecção, use `--v2-stage synthesis`.

## Relação com o resto do repositório

Este dataset não faz parte da dissertação. Os resultados dele vão para a disciplina e não somam
nem substituem os 289 bugs de `dataset/bugs_reais/`. A subpasta `geral/` é
anterior: guarda a triagem inicial do corpus da disciplina (rclpy) e não é lida pelo pipeline.

## Subconjunto de valor errado

`adafruit_valor/` traz quatro bugs de drivers de sensores da Adafruit que devolvem um número errado sem
levantar exceção, cada um com uma propriedade tirada do datasheet, para testar a hipótese da especificação.
Ver `adafruit_valor/README.md`.
