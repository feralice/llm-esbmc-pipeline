# Candidatos a bugs reais de software Python ciber-físico (PGENE601)

Lista de 08/10/2026 para aprovação. Fonte: pull requests de correção já aceitos pelos mantenedores
(o aceite é a validação do bug). Filtro: título indica falha de execução; correção pequena (até 30
linhas) em código Python que não é teste. Próximo passo, depois da aprovação: conferir em cada
diff a função e a expressão do bug e se ele quebra com um dado vindo de fora.

Marque com x os aprovados.

## Decodificar pacote ou mensagem do hardware (o perfil central do projeto)

| ok | PR | linhas | teste no PR | o que é |
|---|---|---|---|---|
| [ ] | [pymodbus-dev/pymodbus#2980](https://github.com/pymodbus-dev/pymodbus/pull/2980) | 8 | sim | lê byte count de um pacote sem conferir o tamanho |
| [ ] | [pymodbus-dev/pymodbus#3017](https://github.com/pymodbus-dev/pymodbus/pull/3017) | 11 | sim | FC17: identificador decodificado com um byte a mais (resultado errado) |
| [ ] | [pymodbus-dev/pymodbus#2045](https://github.com/pymodbus-dev/pymodbus/pull/2045) | 2 | sim | erro no decodificador |
| [ ] | [pymodbus-dev/pymodbus#2174](https://github.com/pymodbus-dev/pymodbus/pull/2174) | 2 | não | ID de transação estoura |
| [ ] | [pymodbus-dev/pymodbus#1627](https://github.com/pymodbus-dev/pymodbus/pull/1627) | 5 | não | início de quadro errado em resposta de exceção |
| [ ] | [ArduPilot/pymavlink#1259](https://github.com/ArduPilot/pymavlink/pull/1259) | 2 | não | struct.error ao decodificar item curto de log de voo |
| [ ] | [bluerobotics/ping-python#80](https://github.com/bluerobotics/ping-python/pull/80) | 2 | não | sonar subaquático: quebra quando o parse falha |
| [ ] | [FreeOpcUa/opcua-asyncio#1803](https://github.com/FreeOpcUa/opcua-asyncio/pull/1803) | 5 | sim | objeto com tamanho -1 (ausente) quebra o parse |
| [ ] | [FreeOpcUa/opcua-asyncio#1955](https://github.com/FreeOpcUa/opcua-asyncio/pull/1955) | 2 | sim | número de sequência uint16 estoura |
| [ ] | [FreeOpcUa/opcua-asyncio#1131](https://github.com/FreeOpcUa/opcua-asyncio/pull/1131) | 4 | não | off-by-one no ponto de continuação |
| [ ] | [adafruit/Adafruit_Blinka#501](https://github.com/adafruit/Adafruit_Blinka/pull/501) | 6 | não | payload I2C vazio |

## Ler arquivos e logs de barramento (CAN, drone)

| ok | PR | linhas | teste no PR | o que é |
|---|---|---|---|---|
| [ ] | [hardbyte/python-can#1811](https://github.com/hardbyte/python-can/pull/1811) | 5 | não | leitor de log ASC quebra numa linha 'Start of Measurement' |
| [ ] | [cantools/cantools#818](https://github.com/cantools/cantools/pull/818) | 19 | sim | leitor de log candump quebra em linha ERRORFRAME |
| [ ] | [cantools/cantools#146](https://github.com/cantools/cantools/pull/146) | 15 | sim | quebra quando o índice MUX não vem no arquivo DBC |
| [ ] | [cantools/cantools#230](https://github.com/cantools/cantools/pull/230) | 2 | sim | grupos de sinais vazios |
| [ ] | [cantools/cantools#595](https://github.com/cantools/cantools/pull/595) | 3 | sim | AttributeError com comentário vazio em ARXML |
| [ ] | [cantools/cantools#444](https://github.com/cantools/cantools/pull/444) | 4 | não | exceção quando um tamanho vem zero em ARXML |
| [ ] | [cantools/cantools#804](https://github.com/cantools/cantools/pull/804) | 2 | sim | UnboundLocalError ao exportar |
| [ ] | [cantools/cantools#841](https://github.com/cantools/cantools/pull/841) | 25 | sim | valores negativos em codificador sem sinal (resultado errado) |

## Valor ausente ou None vindo do dispositivo ou da configuração

| ok | PR | linhas | teste no PR | o que é |
|---|---|---|---|---|
| [ ] | [hardbyte/python-can#2026](https://github.com/hardbyte/python-can/pull/2026) | 4 | não | timeout None vira TypeError |
| [ ] | [hardbyte/python-can#1599](https://github.com/hardbyte/python-can/pull/1599) | 2 | sim | KeyError no socketcan |
| [ ] | [hardbyte/python-can#1466](https://github.com/hardbyte/python-can/pull/1466) | 3 | não | TypeError no driver PCAN |
| [ ] | [hardbyte/python-can#1293](https://github.com/hardbyte/python-can/pull/1293) | 4 | não | AttributeError ao montar erro do driver |
| [ ] | [hardbyte/python-can#1249](https://github.com/hardbyte/python-can/pull/1249) | 2 | não | quebra garantida no driver usb2can |
| [ ] | [hardbyte/python-can#1868](https://github.com/hardbyte/python-can/pull/1868) | 2 | sim | regex errada ao ler configuração |
| [ ] | [cantools/cantools#779](https://github.com/cantools/cantools/pull/779) | 2 | não | filtro None quebra o monitor |
| [ ] | [pyserial/pyserial#820](https://github.com/pyserial/pyserial/pull/820) | 13 | não | UnboundLocalError |
| [ ] | [pyserial/pyserial#149](https://github.com/pyserial/pyserial/pull/149) | 2 | não | TypeError ao receber dados |
| [ ] | [ArduPilot/pymavlink#1217](https://github.com/ArduPilot/pymavlink/pull/1217) | 5 | não | erro de tipo no cache |
| [ ] | [ArduPilot/pymavlink#709](https://github.com/ArduPilot/pymavlink/pull/709) | 4 | sim | erro de tipo |
| [ ] | [ArduPilot/MAVProxy#1032](https://github.com/ArduPilot/MAVProxy/pull/1032) | 2 | não | GPS simulado: atributo de None |
| [ ] | [ArduPilot/MAVProxy#881](https://github.com/ArduPilot/MAVProxy/pull/881) | 2 | não | exceção na tarefa de FTP do drone |
| [ ] | [dronekit/dronekit-python#890](https://github.com/dronekit/dronekit-python/pull/890) | 2 | não | comparação None > int no Python 3 |
| [ ] | [adafruit/Adafruit_Blinka#434](https://github.com/adafruit/Adafruit_Blinka/pull/434) | 7 | não | falta checar None ao desligar o PWM |
| [ ] | [FreeOpcUa/opcua-asyncio#1826](https://github.com/FreeOpcUa/opcua-asyncio/pull/1826) | 9 | não | nonce ou certificado podem vir None |
| [ ] | [FreeOpcUa/opcua-asyncio#671](https://github.com/FreeOpcUa/opcua-asyncio/pull/671) | 5 | não | quebra se o servidor não informa URLs |
| [ ] | [micropython/micropython-lib#1089](https://github.com/micropython/micropython-lib/pull/1089) | 13 | sim | OverflowError em re.groups |

## Robótica (ROS 2)

| ok | PR | linhas | teste no PR | o que é |
|---|---|---|---|---|
| [ ] | [ros2/ros2cli#1112](https://github.com/ros2/ros2cli/pull/1112) | 2 | não | ROS_DOMAIN_ID vazio |
| [ ] | [ros2/ros2cli#1026](https://github.com/ros2/ros2cli/pull/1026) | 2 | não | flags vazias ao converter para texto |
| [ ] | [ros2/ros2cli#984](https://github.com/ros2/ros2cli/pull/984) | 2 | sim | string vazia ao definir parâmetro |
| [ ] | [ros2/rclpy#1669](https://github.com/ros2/rclpy/pull/1669) | 11 | não | lista alterada durante a iteração |
| [ ] | [ros2/rclpy#1299](https://github.com/ros2/rclpy/pull/1299) | 9 | não | AttributeError _logger no servidor de ações |
| [ ] | [ros2/launch#969](https://github.com/ros2/launch/pull/969) | 13 | sim | parse de respawn_max_retries vindo como texto no YAML |
| [ ] | [ros2/launch#470](https://github.com/ros2/launch/pull/470) | 11 | sim | bug em TimerAction.parse |
| [ ] | [ros2/launch#339](https://github.com/ros2/launch/pull/339) | 2 | não | erro no parse de ExecuteProcess |

Total: 45 candidatos.
