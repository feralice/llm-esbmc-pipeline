# Candidatos extras de bugs reais em software Python ciber-físico (PGENE601)

Data: 12/10/2026. Complementa `cps_candidatos_2026-10-08.md` (45 PRs) e `cps_preselecao_2026-10-12.md`
(20 aprovados, 25 descartados). Nenhum PR desses dois arquivos se repete aqui.

Método: busca só de leitura com `gh search prs --merged` em 60 repositórios do domínio (protocolos
industriais, GNSS, CAN/UDS/OBD, MQTT, drones, ROS 2, drivers Adafruit/CircuitPython, PLC), com termos de
falha de execução (crash, IndexError, KeyError, TypeError, AttributeError, ValueError, None, empty,
struct.error, out of range, UnboundLocal, ZeroDivision). Cerca de 2.300 títulos triados; uns 140 PRs
abertos com `gh pr view` e `gh pr diff`. Nos casos em que a descrição não bastava, o arquivo foi lido
no commit pai do merge (`<merge>^`), e isso confirmou udsoncan#198, python-can#713, dronekit#431,
MAVProxy#1380 e gpiozero#716. Todos os PRs abaixo estão MERGED; a versão com bug é sempre `<merge>^`.

Filtro: o mesmo da pré-seleção. Exceção nativa que nasce na própria função com dado vindo de fora,
patch pequeno, função síncrona e recortável, sem thread, async ou dependência de SO. Bônus segue a
mesma numeração: #8247 método/atributo em None, #8248 aritmética ou comparação com None, #8249 `in` em
Optional, #8251 `int()`/`float()` de string, #8252 UnboundLocalError, #8253 getattr literal, #8258 `*xs`.

Coluna "patch": linhas adicionadas/removidas fora de teste e changelog.

Marque com x os aprovados.

## 1. Decodificar pacote ou mensagem (13)

| ok | PR | merge | função (arquivo) | expressão do bug e onde estoura | exceção | origem do dado | patch | bônus | risco |
|---|---|---|---|---|---|---|---|---|---|
| [x] | [pymodbus#2921](https://github.com/pymodbus-dev/pymodbus/pull/2921) | 5e0816c | `FramerTLS.decode` (`pymodbus/framer/tls.py`) | `dev_id = int(data[6])` sem checar `len(data)` | IndexError | quadro Modbus/TLS recebido da rede | +3/-1 | não | muito baixo; função de 3 linhas, só bytes e int |
| [x] | [pymodbus#1738](https://github.com/pymodbus-dev/pymodbus/pull/1738) | 8de66a2 | `ReadDeviceInformationResponse.calculateRtuFrameSize` (`pymodbus/mei_message.py`) | laço com `struct.unpack(">BB", buffer[size:size+2])` anda além do fim do quadro parcial | struct.error | quadro RTU parcial vindo da serial | +8/-5 | não | classmethod curto; precisa do modelo de `struct.unpack` com fatia curta (mesma necessidade de pymodbus#2980) |
| [x] | [pymodbus#2977](https://github.com/pymodbus-dev/pymodbus/pull/2977) | 8a3be74 | `WriteMultipleRegistersRequest.decode` (`pymodbus/pdu/register_message.py`) | `range(5, count*2+5, 2)` confia na quantidade declarada; `struct.unpack(">H", data[idx:idx+2])` com fatia vazia | struct.error | PDU de escrita FC16 vinda do cliente | +24/-8 | não | o mesmo erro aparece em `ReadWriteMultipleRegistersRequest.decode`; escolher uma |
| [x] | [Adafruit MiniMQTT#5](https://github.com/adafruit/Adafruit_CircuitPython_MiniMQTT/pull/5) | 25b344a | `MQTT.connect` (`adafruit_minimqtt.py`) | `rc = self._sock.read(3)` e depois `CONNACK_ERRORS[rc[3]]` quando o broker recusa | IndexError | CONNACK do broker MQTT | +1/-1 | não | só estoura com código de retorno diferente de 0; socket vira parâmetro `bytes` |
| [x] | [micropython-lib#1149](https://github.com/micropython/micropython-lib/pull/1149) | a7fe5c3 | `MQTTClient.connect` (`umqtt/simple.py`) | `resp = self.sock.read(4)`; `resp[0]` com resposta curta ou None | IndexError ou TypeError | CONNACK curto ou timeout do socket | +6/-4 | parcial (None subscrito) | recortar só o trecho após o `read`; o `assert` original também conta |
| [x] | [pyrtcm#34](https://github.com/semuconsulting/pyrtcm/pull/34) | 36fae91 | `RTCMMessage.__str__` (`pyrtcm/rtcmmessage.py`) | `RTCM_MSGIDS[self.identity]` com tipo de mensagem indefinido | KeyError | fluxo RTCM3 de correção GNSS (NTRIP) | +6/-6 | não | `__str__` percorre `__dict__`; recortar o teste do dicionário |
| [x] | [pycomm3#331](https://github.com/ottowayi/pycomm3/pull/331) | a466f88 | `PCCCStringType._slc_string_swap` (`pycomm3/cip/pccc.py`) | `for x1, x2 in (data[i:i+2] ...)` com comprimento ímpar | ValueError (unpack) | string lida do CLP SLC ou enviada a ele | +53/-12 | não | patch grande, mas a função com bug tem 4 linhas; usa `itertools.chain`, que pode virar laço |
| [x] | [udsoncan#291](https://github.com/pylessard/python-udsoncan/pull/291) | 48fabc4 | `AsciiCodec.decode` (`udsoncan/common/DidCodec.py`) | `string_bin.decode('ascii')` com VIN em 0xFF | UnicodeDecodeError | resposta ReadDataByIdentifier da ECU | +1/-1 | não | suporte do ESBMC a `bytes.decode` com erro é incerto; testar antes |
| [x] | [udsoncan#198](https://github.com/pylessard/python-udsoncan/pull/198) | 18027a9 | `Client.send_request` (`udsoncan/client.py`) | `wait_frame` devolve None sem exceção; `timeout_name_to_report` só é atribuída no `except` | UnboundLocalError | conexão ISO-TP sem resposta da ECU | +15/-15 | #8252 | função enorme; recortar o laço de espera com `recv_payload` nondet Optional |
| [x] | [Adafruit GPS#127](https://github.com/adafruit/Adafruit_CircuitPython_GPS/pull/127) | c7c8d34 | `_parse_degrees` (`adafruit_gps.py`) | `raw = nmea_data.split(".")` e `raw[1]` quando o receptor omite o ponto decimal | IndexError (também ValueError em `int(raw[0])`) | sentença NMEA do GPS | +40/-11 | #8251 | função pura de 6 linhas; patch grande porque cria helper |
| [x] | [Adafruit GPS#126](https://github.com/adafruit/Adafruit_CircuitPython_GPS/pull/126) | 3408f29 | `GPS._update_timestamp_utc` (`adafruit_gps.py`) | `int(time_utc[0:2])` e `int(date[0:2])` com campo vazio ou truncado | ValueError | campos de hora e data da sentença NMEA | +26/-7 | #8251 | depende de `time.struct_time`; recortar até o cálculo de dia/mês/ano |
| [x] | [Adafruit GPS#60](https://github.com/adafruit/Adafruit_CircuitPython_GPS/pull/60) | cc4c9df | `GPS.update` e `_parse_talker` (`adafruit_gps.py`) | `data_type[0] == b"P"` com tipo de sentença vazio | IndexError | sentença NMEA corrompida na serial | +2/-0 | não | exceção nasce em `_parse_talker`, chamada por `update`; harness liga as duas |
| [x] | [scapy#5089](https://github.com/secdev/scapy/pull/5089) | c6ab6a8 | condição de `msgid` e `length_from` de `MQTTPublish` (`scapy/contrib/mqtt.py`) | `pkt.underlayer.QOS` com `underlayer` None | AttributeError | pacote MQTT PUBLISH sem camada fixa | +6/-5 | #8247 | o código são lambdas em `fields_desc`; recortar como função `f(pkt)` |

## 2. Logs e arquivos (5)

| ok | PR | merge | função (arquivo) | expressão do bug e onde estoura | exceção | origem do dado | patch | bônus | risco |
|---|---|---|---|---|---|---|---|---|---|
| [x] | [python-can#713](https://github.com/hardbyte/python-can/pull/713) | 216ed73 | `CanutilsLogReader.__iter__` (`can/io/canutils.py`) | `data=dataBin` quando a primeira linha do log é quadro remoto (`R`) | UnboundLocalError | log `candump -L` | +3/-0 | #8252 | só estoura se o RTR vier antes de qualquer quadro de dados; recortar o corpo do laço recebendo a linha |
| [x] | [python-can#225](https://github.com/hardbyte/python-can/pull/225) | 0d27073 | `ASCReader.__iter__` (`can/io/asc.py`) | `(timestamp, channel, dummy) = temp.split(None, 2)` em linha com menos de três campos | ValueError (unpack) | arquivo `.asc` do CANoe | +12/-1 | não | desempacotamento de tupla de tamanho variável; checar suporte do frontend |
| [x] | [pymavlink#1058](https://github.com/ArduPilot/pymavlink/pull/1058) | 6929b9f | `DFReader_binary.init_arrays_fast` (`DFReader.py`) | `self.name_to_id['UNIT']` em log sem mensagem UNIT (e o mesmo para MULT) | KeyError | log `.BIN` gerado por ferramenta que não é autopiloto | +42/-39 (2 de lógica, resto reindentação) | não | mesma função de pymavlink#1259, mas bug diferente; recortar o bloco UNIT |
| [x] | [MAVProxy#989](https://github.com/ArduPilot/MAVProxy/pull/989) | b228d03 | `LogModule.log_status` (`mavproxy_log.py`) | `pct = (100.0*file_size)/size` com `m.size == 0` | ZeroDivisionError | LOG_ENTRY de log vazio enviado pelo drone | +3/-0 | não | muito baixo; `m` vira objeto simples com `size` nondet |
| [x] | [MAVProxy#741](https://github.com/ArduPilot/MAVProxy/pull/741) | 122a10c | `LogModule.log_status` (`mavproxy_log.py`) | `max(self.download_set)` antes de chegar qualquer bloco | ValueError | estado do download de log do drone | +3/-1 | não | mesma função de MAVProxy#989; pode virar um caso só com duas propriedades |

## 3. None do dispositivo ou da configuração (7)

| ok | PR | merge | função (arquivo) | expressão do bug e onde estoura | exceção | origem do dado | patch | bônus | risco |
|---|---|---|---|---|---|---|---|---|---|
| [x] | [dronekit#431](https://github.com/dronekit/dronekit-python/pull/431) | 7f1f5a4 | `Vehicle.battery` e `Battery.__init__` (`dronekit/lib/__init__.py`) | `voltage / 1000.0` com `_voltage` None antes do primeiro SYS_STATUS | TypeError | telemetria de bateria ainda não recebida | +3/-1 (lib) | #8248 | baixo; exceção nasce no construtor chamado pela property |
| [x] | [Adafruit PIO_UART#6](https://github.com/adafruit/Adafruit_CircuitPython_PIO_UART/pull/6) | 66046da | `UART.read` (`adafruit_pio_uart.py`) | `n = self.readinto(buf)` devolve None com timeout 0; estoura em `n < len(buf)` | TypeError | leitura da UART sem dados | +1/-1 | #8248 | muito baixo; `readinto` vira stub que devolve Optional[int] |
| [x] | [MAVProxy#1572](https://github.com/ArduPilot/MAVProxy/pull/1572) | cfa6203 | `FTPModule.send` (`mavproxy_ftp.py`) | `self.master.mav.file_transfer_protocol_send(...)` sem link | AttributeError | ausência de conexão com o veículo | +3/-0 | #8247 | mesmo padrão de MAVProxy#1032 já aprovado; escolher se quiser variedade |
| [x] | [MAVProxy#1447](https://github.com/ArduPilot/MAVProxy/pull/1447) | b344a7a | `BatteryModule.cmd_bat` (`mavproxy_battery.py`) | `self.battery_level[0]` antes de chegar BATTERY_STATUS | KeyError | dict preenchido por mensagens do drone | +3/-0 | não | baixo; dict vazio ou com chave nondet |
| [x] | [gpiozero#716](https://github.com/gpiozero/gpiozero/pull/716) | 870f051 | `CPUTemperature.value` (`gpiozero/other_devices.py`) | `(temperature - min_temp) / (max_temp - min_temp)` com `min_temp == max_temp` | ZeroDivisionError | parâmetros de configuração do dispositivo | +2/-0 | não | a correção fica no `__init__` e o estouro na property; leitura do sensor vira nondet |
| [x] | [Adafruit SimpleIO#43](https://github.com/adafruit/Adafruit_CircuitPython_SimpleIO/pull/43) | d1ea1bb | `map_range` (`simpleio.py`) | `/ (in_max - in_min)` com faixa de entrada degenerada | ZeroDivisionError | faixa configurada para mapear leitura de sensor | +10/-1 | não | muito baixo; função pura, ótima como caso de calibração |
| [x] | [pyspartn#4](https://github.com/semuconsulting/pyspartn/pull/4) | 76d2092 | `SPARTNMessage.__init__` (`pyspartn/spartnmessage.py`) | `bytes.fromhex(key)` com `key` None quando `MQTTKEY` não está definida | TypeError | variável de ambiente ou argumento da chave de decifração | +36/-6 (5 no ponto do bug) | não | `os.getenv` vira parâmetro Optional[str]; resto do construtor recortável |

## 4. Robótica e veículos (4)

| ok | PR | merge | função (arquivo) | expressão do bug e onde estoura | exceção | origem do dado | patch | bônus | risco |
|---|---|---|---|---|---|---|---|---|---|
| [x] | [dronekit#611](https://github.com/dronekit/dronekit-python/pull/611) | 9b27f34 | `Vehicle._is_mode_available` (`dronekit/__init__.py`) | `mode_code in self._mode_mapping_bynumber` quando `mavutil.mode_mapping_bynumber` devolve None para tipo de veículo desconhecido | TypeError | tipo de veículo do HEARTBEAT | +4/-1 | #8249 | baixo; único candidato com `in` em Optional |
| [x] | [MAVProxy#1380](https://github.com/ArduPilot/MAVProxy/pull/1380) | 0a44e17 | `MPSlipMapPanel.click_position_text` (`mp_slipmap_ui.py`) | compara `terrain_height == "?"` (nunca verdade) e faz `terrain_height - self.last_terrain_height` com altura None | TypeError | mapa de elevação sem dado no ponto clicado | +1/-1 | #8248 | arquivo de interface wx; recortar o trecho de cálculo com elevação Optional[float] |
| [x] | [ros2cli#370](https://github.com/ros2/ros2cli/pull/370) | 096de53 | `_check_network_config_helper` (`ros2doctor/api/network.py`) | `iface.get('flags').lower()` em interface sem `flags` | AttributeError | interfaces de rede lidas por `ifcfg` | +10/-8 | #8247 | baixo; `ifcfg.interfaces()` vira dict de dicts como parâmetro |
| [x] | [ros2cli#646](https://github.com/ros2/ros2cli/pull/646) | a9def45 | `ListVerb.main` (`ros2param/verb/list.py`) | após imprimir a exceção, segue com `response.result.names` e `response` None | AttributeError | resposta do serviço de parâmetros do nó | +1/-0 | #8247 | `main` usa rclpy; recortar o laço de impressão com `future.result()` Optional |

## 5. Outros (1)

| ok | PR | merge | função (arquivo) | expressão do bug e onde estoura | exceção | origem do dado | patch | bônus | risco |
|---|---|---|---|---|---|---|---|---|---|
| [x] | [paho-mqtt#118](https://github.com/eclipse-paho/paho.mqtt.python/pull/118) | dcd9dba | `Client._host_matches_cert` (`paho/mqtt/client.py`) | `host.split(".", 1)[1]` com hostname sem ponto e certificado curinga | IndexError | hostname configurado e campo do certificado do broker | +3/-3 | não | baixo; função pura de strings |

## 6. Lidos, mais fracos (6)

Valem só se faltar caso em algum grupo.

| PR | merge | por que ficou de fora |
|---|---|---|
| [python-OBD#46](https://github.com/brendan-w/python-OBD/pull/46) | f8a464f | `unhexlify(raw)` com quadro CAN de tamanho ímpar dá `binascii.Error` em `parse_frame`; bom dado externo, mas depende de modelar `binascii` |
| [python-OBD#116](https://github.com/brendan-w/python-OBD/pull/116) | faaee8b | `buffer.decode()` com byte inválido do ELM327; mesma classe de udsoncan#291, dentro de `__read` com serial |
| [cantools#477](https://github.com/cantools/cantools/pull/477) | b750619 | `element['signal']` sem a chave em DBC com BU_BO_REL dá KeyError no dump; patch de 55 linhas e gerador de texto longo |
| [opcua-asyncio#1217](https://github.com/FreeOpcUa/opcua-asyncio/pull/1217) | b380a56 | `*method.InputArguments` com None dá TypeError; seria o único caso perto de #8258, mas está em método `async` |
| [pyvisa#913](https://github.com/pyvisa/pyvisa/pull/913) | 8a88ce2 | `(95 + 0xFFFF).to_bytes(1, "big")` dá OverflowError com GPIB sem endereço secundário; suporte do ESBMC a `int.to_bytes` é incerto |
| [opcua-asyncio#1984](https://github.com/FreeOpcUa/opcua-asyncio/pull/1984) | 6c642c5 | `cls(b)` de `IntEnum` com bit indefinido dá ValueError; depende de Enum no frontend |

Também lidos e descartados, para não reabrir: pymavlink#380 (a condição do patch parece invertida),
gpiozero#530 (o KeyError já era capturado e virava PinUnknownPi), pymodbus#2861, #2830 e #2926 (resultado
errado sem exceção ou `async`), isotp#160 (ValueError lançado de propósito), pynmeagps#26 e pyubx2#74
(exceção própria ou só mensagem), pymavlink#906 (comparação sempre falsa, sem exceção), python-can#1767 e
#1613 (ctypes de driver), Adafruit MAX31856#5 e Wiznet5k#72 (falham sempre, sem depender do dado),
paho-mqtt#955 (resultado errado), MAVProxy#1669 (NameError estático).

## 7. Reavaliação das 7 reservas da pré-seleção

| PR | entra? | motivo |
|---|---|---|
| [opcua-asyncio#1803](https://github.com/FreeOpcUa/opcua-asyncio/pull/1803) | não | a falha continua noutro decodificador; com pymodbus#2921, pymodbus#1738 e os casos de GPS o grupo de decodificação já não precisa dele |
| [cantools#818](https://github.com/cantools/cantools/pull/818) | não | regex mais `binascii`; python-can#713 e python-can#225 cobrem log de barramento com exceção nativa local |
| [cantools#146](https://github.com/cantools/cantools/pull/146) | não | IndexError só depois de `message.decode`, com bitstruct por baixo |
| [python-can#1249](https://github.com/hardbyte/python-can/pull/1249) | só com teste rápido | vale entrar se um programa de 3 linhas com `dict.get(k, d=...)` passar pelo frontend e der TypeError; senão, fica fora |
| [cantools#779](https://github.com/cantools/cantools/pull/779) | não | o None só estoura na interface curses |
| [ros2cli#984](https://github.com/ros2/ros2cli/pull/984) | não | ros2cli#370 e ros2cli#646 dão AttributeError em None dentro da própria função, sem o setter gerado do rosidl |
| [launch#339](https://github.com/ros2/launch/pull/339) | não | erro de aridade que o frontend tende a recusar antes de verificar |

## 8. Contagem

| grupo | novos (seção 1 a 5) | com bônus ESBMC | mais fracos (seção 6) |
|---|---|---|---|
| decodificar pacote ou mensagem | 13 | 4 (#8251 em dois, #8252, #8247) e 1 parcial | 2 |
| logs e arquivos | 5 | 1 (#8252) | 1 |
| None do dispositivo ou da configuração | 7 | 3 (#8248 em dois, #8247) | 3 |
| robótica e veículos | 4 | 4 (#8249, #8248, #8247 em dois) | 0 |
| outros | 1 | 0 | 0 |
| total | 30 | 12 e 1 parcial | 6 |

Observações:

- O grupo de decodificação sai de 4 para até 17 casos, e só um dos novos (scapy#5089) depende de
  framework pesado; nenhum é `async`.
- Bônus por correção nos novos: #8247 em quatro, #8248 em três, #8251 em dois, #8252 em dois e #8249 em
  um. É o primeiro caso de #8249 (dronekit#611). Continuam sem caso #8253 e #8258.
- Dois pares tocam a mesma função: MAVProxy#989 com MAVProxy#741 (`log_status`) e GPS#127 com GPS#126
  (mesmo arquivo). Aprovar os dois de cada par aumenta a contagem sem aumentar a variedade.
- Os mais seguros para começar são pymodbus#2921, MiniMQTT#5, MAVProxy#989, PIO_UART#6, SimpleIO#43,
  python-can#713 e dronekit#611: função curta, exceção nativa na própria linha e dado externo fácil de
  modelar.
