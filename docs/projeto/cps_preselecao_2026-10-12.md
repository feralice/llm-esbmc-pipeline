# Pré-seleção de bugs reais de software Python ciber-físico (PGENE601)

Data: 12/10/2026. Entrada: `cps_candidatos_2026-10-08.md` (45 PRs de correção aceitos).

Método: para cada PR foram lidos título, descrição, arquivos e diff (`gh pr view` e `gh pr diff`),
e, quando a descrição não trazia o traceback, a issue ligada ao PR. Nos casos duvidosos o código da
versão com bug foi conferido diretamente no commit pai do merge. Todos os 45 PRs foram lidos sem
erro, e todos têm merge commit registrado; a versão com bug é sempre `<merge>^`.

Critério de prioridade: exceção nativa do Python que nasce na própria função, patch pequeno, dado
vindo de hardware, arquivo ou configuração, função sem async e sem dependência pesada. Ganham bônus
as construções cobertas pelas correções recentes do ESBMC-Python (#8247 método/atributo em None,
#8248 aritmética ou comparação com None, #8249 `in` em Optional, #8251 `int()`/`float()` de string,
#8252 UnboundLocalError, #8253 getattr literal, #8258 `*xs`).

Marque com x os aprovados.

## 1. Pré-seleção recomendada (20)

| ok | PR | grupo | merge | função (arquivo) | expressão do bug | exceção | origem do dado | bônus | risco |
|---|---|---|---|---|---|---|---|---|---|
| [x] | [pymodbus#2980](https://github.com/pymodbus-dev/pymodbus/pull/2980) | decodificação | 09a3cb2 | `ReadFileRecordRequest.decode` (`pdu/file_message.py`) | `byte_count = int(data[0])` sem comparar com `len(data)`; estoura em `struct.unpack(">BHHH", data[count:count+7])` | struct.error (IndexError se `data` vazio) | PDU Modbus recebido da rede ou do dispositivo | não | modelo de `struct.unpack` com buffer curto; mesmo padrão em mais duas funções do PR, escolher uma |
| [x] | [pymavlink#1259](https://github.com/ArduPilot/pymavlink/pull/1259) | decodificação | 075f572 | `DFReader_binary.init_arrays_fast` (`DFReader.py`) | `body = data[ofs+3:ofs+fmt_fmt.len]` fica curto no fim do arquivo | struct.error em `struct.unpack(fmt_fmt.msg_struct, body)` | arquivo `.BIN` de log de voo truncado | não | função longa com mmap; recortar só o laço que lê o FMT |
| [x] | [opcua-asyncio#1131](https://github.com/FreeOpcUa/opcua-asyncio/pull/1131) | decodificação | e680d7e | `HistoryDict.read_node_history` (`server/history.py`) | `results[self.max_history_data_response_size + 1]` quando `len(results) == max + 1` | IndexError | histórico de valores armazenado no servidor OPC UA | não | método `async` (corpo síncrono, recortável); o mesmo erro aparece em `read_event_history` |
| [x] | [opcua-asyncio#1955](https://github.com/FreeOpcUa/opcua-asyncio/pull/1955) | decodificação | baed488 | `DataSetWriter.generate_uadp_dataset` (`pubsub/writer.py`) | `self._seq_no += 1` sem limite de uint16 | struct.error no `struct.pack('<H')` do serializador | contador de mensagens publicadas | não | `async` e exceção em outra função; o harness precisa ligar contador e pack, com estado inicial nondet |
| [x] | [python-can#1811](https://github.com/hardbyte/python-can/pull/1811) | logs CAN | d34b2d6 | `ASCReader.__iter__` e `_process_fd_can_frame` (`can/io/asc.py`) | linha `CANFD Start of measurement` não é pulada; `channel = 'Start'` | ValueError em `int(channel)` | arquivo `.asc` gerado pelo CANoe | #8251 | `__iter__` usa regex e arquivo; recortar `_process_fd_can_frame` recebendo a linha |
| [x] | [cantools#595](https://github.com/cantools/cantools/pull/595) | logs CAN | 36a9cf1 | `SystemLoader._load_comments` (`arxml/system_loader.py`) | `l_2.text.split('\n')` com `text` None | AttributeError | arquivo ARXML com comentário `<L-2/>` vazio | #8247 | ElementTree vira stub com `text: Optional[str]` |
| [x] | [cantools#804](https://github.com/cantools/cantools/pull/804) | logs CAN | 01e7f20 | `_dump_signals` (`formats/sym.py`) | `if signals:` com `signals` atribuída só dentro do laço | UnboundLocalError com `database.messages` vazio | banco CAN carregado de arquivo DBC/SYM | #8252 | baixo; só precisa de objetos simples para mensagem e sinal |
| [x] | [python-can#1599](https://github.com/hardbyte/python-can/pull/1599) | None do dispositivo | b291f80 | `find_available_interfaces` (`socketcan/utils.py`) | `i["link_type"]` em entrada sem a chave | KeyError | saída JSON de `ip -json link` do sistema | não | `subprocess` sai; a lista de dicts entra como parâmetro |
| [x] | [python-can#1293](https://github.com/hardbyte/python-can/pull/1293) | None do dispositivo | ed6cd66 | `IscanError.__init__` (`interfaces/iscan.py`) | `self.ERROR_CODES[self.error_code]` e `self.function` antes de `super().__init__` | AttributeError (atributo ainda inexistente) | código de erro devolvido pela DLL do driver | não | atributo inexistente, não None; subclasse de exceção pode esbarrar no frontend |
| [x] | [pyserial#820](https://github.com/pyserial/pyserial/pull/820) | None do dispositivo | b0b93cb | `Serial.read` (`serial/serialposix.py`) | `if fd == self.pipe_abort_read_r` depois do `for` quando `poll()` devolve lista vazia | UnboundLocalError | resultado de `poll()` na porta serial (timeout sem dados) | #8252 | IO real (`select.poll`, `os.read`) precisa de stub nondet |
| [x] | [pyserial#149](https://github.com/pyserial/pyserial/pull/149) | None do dispositivo | 1eb040e | `FramedPacket.data_received` (`serial/threaded/__init__.py`) | `self.packet.append(byte)` com `byte` do tipo `bytes` | TypeError (bytearray.append exige int) | bytes recebidos da porta serial | não | `serial.iterbytes` é fácil de inlinar; suporte do ESBMC a esse TypeError é incerto |
| [x] | [pymavlink#1217](https://github.com/ArduPilot/pymavlink/pull/1217) | None do dispositivo | 56a3bb0 | `add_message` (`mavutil.py`) | `messages[mtype]._instances[instance_value] = msg` com `_instances` None | TypeError | fluxo MAVLink que passa de v1 para v2 | não | `getattr(msg, msg._instance_field)` com nome variável e `copy.copy` |
| [x] | [MAVProxy#1032](https://github.com/ArduPilot/MAVProxy/pull/1032) | None do dispositivo | 6403754 | `FakeGPSModule.idle_task` (`mavproxy_fakegps.py`) | `self.master.mav.gps_input_send(...)` com `master` None | AttributeError | ausência de link com o veículo | #8247 | `time.time()` e settings do módulo viram parâmetros |
| [x] | [MAVProxy#881](https://github.com/ArduPilot/MAVProxy/pull/881) | None do dispositivo | 4616e6f | `FTPModule.check_read_send` (`mavproxy_ftp.py`) | `now - self.last_gap_send` com o None posto no `__init__` | TypeError | lacunas de leitura FTP reportadas pelo drone | #8248 | o bug nasce no `__init__`, outra função; harness monta o objeto |
| [x] | [dronekit#890](https://github.com/dronekit/dronekit-python/pull/890) | None do dispositivo | e412e95 | `Vehicle.is_armable` (`dronekit/__init__.py`) | `self.gps_0.fix_type > 1` com `fix_type` None | TypeError | GPS ainda sem mensagem `GPS_RAW_INT` | #8248 | baixo; property curta |
| [x] | [Adafruit_Blinka#434](https://github.com/adafruit/Adafruit_Blinka/pull/434) | None do dispositivo | 17b9bef | `PWMOut.deinit` (`bcm283x/pulseio/PWMOut.py`) | `self._pwmpin.stop()` com `_pwmpin` None | AttributeError | sequência de uso do pino (deinit repetido) | #8247 | `RPi.GPIO` global precisa de stub; dado vem do uso, não do sensor |
| [x] | [opcua-asyncio#1826](https://github.com/FreeOpcUa/opcua-asyncio/pull/1826) | None do dispositivo | f12f3e1 | `UaProcessor._process_message` (`server/uaprocessor.py`) | `peer_certificate + params.ClientNonce` com nonce None | TypeError | pedido CreateSession enviado pelo cliente | #8248 | `async` e função enorme; recortar só o ramo CreateSession |
| [x] | [opcua-asyncio#671](https://github.com/FreeOpcUa/opcua-asyncio/pull/671) | None do dispositivo | 49b611b | `application_to_strings` (`asyncua/tools.py`) | `for url in app.DiscoveryUrls` com None | TypeError | descrição de aplicação devolvida pelo servidor | não | baixo; função síncrona e autocontida |
| [x] | [ros2cli#1112](https://github.com/ros2/ros2cli/pull/1112) | ROS 2 | efae7a7 | `get_port` (`ros2cli/daemon/__init__.py`) | `int(os.environ.get('ROS_DOMAIN_ID', 0))` com valor `''` | ValueError | variável de ambiente `ROS_DOMAIN_ID` | #8251 | baixo; `os.environ` vira parâmetro `str` |
| [x] | [ros2cli#1026](https://github.com/ros2/ros2cli/pull/1026) | ROS 2 | 74f6989 | `InterfaceFlags.__str__` (`ros2doctor/api/network.py`) | `return` sem valor quando `flags` vazio; estoura em `str(flags)` no relatório | TypeError (`__str__` devolveu não string) | flags de interface de rede via psutil (vazias no Windows) | não | incerto se o ESBMC checa o tipo de retorno de `__str__` |

## 2. Descartados (25)

Os marcados como reserva são os mais aproveitáveis se algum selecionado cair na hora do harness.

| PR | motivo |
|---|---|
| [pymodbus#3017](https://github.com/pymodbus-dev/pymodbus/pull/3017) | resultado errado sem exceção (identificador com byte a mais) |
| [pymodbus#2045](https://github.com/pymodbus-dev/pymodbus/pull/2045) | fatia longa demais; a exceção só aparece no decodificador seguinte |
| [pymodbus#2174](https://github.com/pymodbus-dev/pymodbus/pull/2174) | `not tid` com tid 0: devolve transação errada, sem exceção |
| [pymodbus#1627](https://github.com/pymodbus-dev/pymodbus/pull/1627) | início de quadro errado, sem exceção |
| [ping-python#80](https://github.com/bluerobotics/ping-python/pull/80) | `e.errno` em exceção genérica dentro de laço de socket e thread |
| [Adafruit_Blinka#501](https://github.com/adafruit/Adafruit_Blinka/pull/501) | comportamento errado no barramento I2C, depende do chip |
| [opcua-asyncio#1803](https://github.com/FreeOpcUa/opcua-asyncio/pull/1803) | reserva: comprimento -1 vira buffer vazio e quebra noutro decodificador |
| [cantools#818](https://github.com/cantools/cantools/pull/818) | reserva: falha nasce numa regex e estoura em `binascii` |
| [cantools#146](https://github.com/cantools/cantools/pull/146) | reserva: IndexError só depois de `message.decode`, dependência pesada |
| [cantools#230](https://github.com/cantools/cantools/pull/230) | erro de gramática do textparser, sem exceção nativa |
| [cantools#444](https://github.com/cantools/cantools/pull/444) | exceção própria do cantools lançada em outra classe |
| [cantools#841](https://github.com/cantools/cantools/pull/841) | gerador de código C; o defeito está no C gerado |
| [python-can#2026](https://github.com/hardbyte/python-can/pull/2026) | TypeError lançado de propósito; mudança de comportamento |
| [python-can#1466](https://github.com/hardbyte/python-can/pull/1466) | depende de Windows, ctypes e `find_library` |
| [python-can#1249](https://github.com/hardbyte/python-can/pull/1249) | reserva: `dict.get(..., d=)` dá TypeError, mas o frontend tende a rejeitar antes |
| [python-can#1868](https://github.com/hardbyte/python-can/pull/1868) | regex de argumentos de linha de comando |
| [cantools#779](https://github.com/cantools/cantools/pull/779) | reserva: o None só estoura na interface curses |
| [pymavlink#709](https://github.com/ArduPilot/pymavlink/pull/709) | string de formatação de mensagem de erro (typo de log) |
| [micropython-lib#1089](https://github.com/micropython/micropython-lib/pull/1089) | offsets vindos de FFI com PCRE2 |
| [ros2cli#984](https://github.com/ros2/ros2cli/pull/984) | reserva: None só quebra no setter gerado do rosidl |
| [rclpy#1669](https://github.com/ros2/rclpy/pull/1669) | threads e lista alterada durante iteração |
| [rclpy#1299](https://github.com/ros2/rclpy/pull/1299) | `async`, atributo `_logger` ausente só no caminho de RCLError |
| [launch#969](https://github.com/ros2/launch/pull/969) | tipo errado aceito, sem exceção local |
| [launch#470](https://github.com/ros2/launch/pull/470) | substituição não resolvida; efeito aparece só na execução do launch |
| [launch#339](https://github.com/ros2/launch/pull/339) | reserva: argumento faltando na chamada, o frontend tende a rejeitar antes |

## 3. Contagem por grupo

| grupo | candidatos | selecionados | com bônus ESBMC | reservas |
|---|---|---|---|---|
| decodificação de pacote ou mensagem | 11 | 4 | 0 | 1 |
| logs CAN e arquivos de barramento | 8 | 3 | 3 | 2 |
| None do dispositivo ou da configuração | 18 | 11 | 6 | 2 |
| ROS 2 | 8 | 2 | 1 | 2 |
| total | 45 | 20 | 10 | 7 |

Observações:

- O grupo de decodificação ficou fraco: dos 11, quatro são resultado errado sem exceção, e dois dos
  quatro selecionados estão em métodos `async` (OPC UA).
- Bônus por correção: #8247 em três casos, #8248 em três, #8251 em dois e #8252 em dois
  (pyserial#820 e cantools#804). Nenhum caso usa #8249, #8253 ou #8258.
- Os mais seguros para começar são dronekit#890, ros2cli#1112, cantools#804, opcua-asyncio#671 e
  cantools#595: função curta, exceção nativa na própria linha e dado externo fácil de modelar.
