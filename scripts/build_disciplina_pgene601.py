"""Build dataset/disciplina_pgene601/ from the accepted fix PRs: 20 in docs/pgene601/cps_preselecao_2026-10-12.md
and 27 of the 30 approved in docs/pgene601/cps_candidatos_extra_2026-10-12.md (see the note in SPECS).

Same layout as dataset/bugs_reais/ (funcao_com_bug/, arquivo_com_bug/, arquivo_corrigido/, patches/,
ground_truths.json, manifest.json, manifest_full.json) and never touches it. The buggy file is the
merge commit's first parent, except for the PRs merged by rebase, where it is the commit before
the PR's first commit. Labels come from reading each patch; rerunning rebuilds the whole folder.
"""

from __future__ import annotations

import ast
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_v2_full_sources import (
    _download,
    _function,
    _one_function,
    _raw_url,
)

from research_pipeline.verify.astutil import expression_nodes

TARGET = ROOT / "dataset" / "disciplina_pgene601"
COHORT = "disciplina_pgene601"
FOLDERS = ("funcao_com_bug", "arquivo_com_bug", "arquivo_corrigido", "patches")
ASYNC_NOTE = (
    "função async: o frontend Python do ESBMC não modela async/await e o motor verify só "
    "aterra FunctionDef; conta para a detecção, o harness exige recorte manual do corpo síncrono"
)

_GPS_INPUT_SEND = """self.master.mav.gps_input_send(time_us, 0, 0, gps_week_ms, gps_week, fix_type,
                               int(gps_lat*1.0e7), int(gps_lon*1.0e7), gps_alt,
                               1.0, 1.0,
                               gps_vel[0], gps_vel[1], gps_vel[2],
                               0.2, 1.0, 1.0,
                               nsats,
                               int(self.FakeGPS_settings.yaw*100))"""

SPECS = [
    {
        "id": "cps_pymodbus_2980",
        "repo": "pymodbus-dev/pymodbus",
        "pr": 2980,
        "merge": "09a3cb23566c65e1c11ed6eaabb5ebf093c266f6",
        "buggy": "4d2c7c67eef068d915a9f103a80a8abb7d789976",
        "source_file": "pymodbus/pdu/file_message.py",
        "function": "ReadFileRecordRequest.decode",
        "expression": "byte_count = int(data[0])",
        "crash": ['struct.unpack(">BHHH", data[count : count + 7])'],
        "expected_type": "struct.error",
        "kind": "excecao_modelavel",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "struct.error: unpack requires a buffer of 7 bytes (byte_count maior que len(data) - 1)",
        "caveat": "o PR corrige o mesmo padrão em mais duas funções (ReadFileRecordResponse.decode e "
        "ReadFifoQueueResponse.decode); só ReadFileRecordRequest.decode está rotulada",
    },
    {
        "id": "cps_pymavlink_1259",
        "repo": "ArduPilot/pymavlink",
        "pr": 1259,
        "merge": "075f572b1427705f08d1f90aef89581203161421",
        "buggy": "774840a8e6450c33cd97a33b86e3af5d3d1ea173",
        "source_file": "DFReader.py",
        "function": "DFReader_binary.init_arrays_fast",
        "expression": "body = data[ofs+3:ofs+fmt_fmt.len]",
        "crash": ["struct.unpack(fmt_fmt.msg_struct, body)"],
        "expected_type": "struct.error",
        "kind": "excecao_modelavel",
        "category": "out_of_bounds",
        "source": "statement_before_insertion",
        "note": "struct.error: unpack requires a buffer of N bytes (FMT truncado no fim do .BIN)",
        "caveat": "função longa com mmap; o harness precisa recortar só o laço que lê os FMT",
    },
    {
        "id": "cps_opcua_1131",
        "repo": "FreeOpcUa/opcua-asyncio",
        "pr": 1131,
        "merge": "e680d7ee57591e08f0a31d75a3c5b1cfbec4e315",
        "buggy": "9d5861adf8c13949e516a567a46751ed23e69285",
        "source_file": "asyncua/server/history.py",
        "function": "HistoryDict.read_node_history / HistoryDict.read_event_history",
        "expression": "results[self.max_history_data_response_size + 1]",
        "crash": [],
        "expected_type": "IndexError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "IndexError: list index out of range quando len(results) == max + 1",
        "caveat": ASYNC_NOTE,
    },
    {
        "id": "cps_opcua_1955",
        "repo": "FreeOpcUa/opcua-asyncio",
        "pr": 1955,
        "merge": "baed48869ee3cd095a40056e82d9979258c38556",
        "buggy": "2889b9beb9671a6430c5a3388ee3834aa4f8d0ab",
        "source_file": "asyncua/pubsub/writer.py",
        "function": "DataSetWriter.generate_uadp_dataset",
        "expression": "self._seq_no += 1",
        "crash": [],
        "expected_type": "struct.error",
        "kind": "excecao_modelavel",
        "category": "integer_overflow",
        "source": "changed_line",
        "note": "struct.error: 'H' format requires 0 <= number <= 65535, no struct.pack do serializador "
        "(outro módulo) depois de 65535 mensagens",
        "caveat": ASYNC_NOTE
        + "; a exceção estoura fora da função, no serializador UADP",
    },
    {
        "id": "cps_pythoncan_1811",
        "repo": "hardbyte/python-can",
        "pr": 1811,
        "merge": "d34b2d62fe103d203967e8ce2d3481d89e9afc18",
        "buggy": "78e4f81f9a3bec1ce4e32b5e85e7b5545053a579",
        "rebase": True,
        "source_file": "can/io/asc.py",
        "function": "ASCReader.__iter__ / ASCReader._process_fd_can_frame",
        "expression": "not ASC_MESSAGE_REGEX.match(line)",
        "crash": ["int(channel)"],
        "expected_type": "ValueError",
        "kind": "excecao_local",
        "category": "type_mismatch",
        "source": "statement_after_insertion",
        "note": "ValueError: invalid literal for int() with base 10: 'Start' (linha 'CANFD Start of "
        "measurement' chega a _process_fd_can_frame)",
        "caveat": "PR integrado por rebase: o pai do merge já é o primeiro commit do PR, então a versão com "
        "bug é o commit anterior ao PR; __iter__ é gerador",
    },
    {
        "id": "cps_cantools_595",
        "repo": "cantools/cantools",
        "pr": 595,
        "merge": "36a9cf1612cd8f791f283b60068d542b8070cbb8",
        "buggy": "d17e9a3d73cc2a412b3dfcb2adbc1df280daaa28",
        "source_file": "cantools/database/can/formats/arxml/system_loader.py",
        "function": "SystemLoader._load_comments",
        "expression": "lang = l_2.attrib.get('L', 'EN')",
        "crash": ["l_2.text.split('\\n')"],
        "expected_type": "AttributeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "statement_after_insertion",
        "note": "AttributeError: 'NoneType' object has no attribute 'split' (<L-2/> vazio no ARXML)",
    },
    {
        "id": "cps_cantools_804",
        "repo": "cantools/cantools",
        "pr": 804,
        "merge": "01e7f2004c2d07ea4946095d0516e8d556a29366",
        "buggy": "58d85e48a5da7fb5d51308c4df2f678c14429c3f",
        "source_file": "src/cantools/database/can/formats/sym.py",
        "function": "_dump_signals",
        "expression": "signals",
        "crash": [],
        "expected_type": "UnboundLocalError",
        "kind": "excecao_local",
        "category": "variable_misuse",
        "source": "changed_line",
        "note": "UnboundLocalError: local variable 'signals' referenced before assignment "
        "(database.messages vazio)",
    },
    {
        "id": "cps_pythoncan_1599",
        "repo": "hardbyte/python-can",
        "pr": 1599,
        "merge": "b291f806ec7ce02e3c8256b3102d3a0e7f22f85d",
        "buggy": "1a3f5e3769aa565ada8c27177a94f7db43d019dc",
        "source_file": "can/interfaces/socketcan/utils.py",
        "function": "find_available_interfaces",
        "expression": 'i["link_type"] == "can"',
        "crash": [],
        "expected_type": "KeyError",
        "kind": "excecao_local",
        "category": "invalid_precondition",
        "source": "changed_line",
        "note": "KeyError: 'link_type' (entrada de `ip -json link` sem a chave)",
        "caveat": "subprocess e json.loads ficam fora do harness; a lista de dicts entra como parâmetro",
    },
    {
        "id": "cps_pythoncan_1293",
        "repo": "hardbyte/python-can",
        "pr": 1293,
        "merge": "ed6cd668b9d81df27bcc6a747047d9cba228a682",
        "buggy": "af55b0a33d30096cb001c168dafb0c3b81ac9fcc",
        "source_file": "can/interfaces/iscan.py",
        "function": "IscanError.__init__",
        "expression": "self.ERROR_CODES[self.error_code]",
        "crash": ["self.function.__name__"],
        "expected_type": "AttributeError",
        "kind": "excecao_local",
        "category": "variable_misuse",
        "source": "changed_line",
        "note": "AttributeError: 'IscanError' object has no attribute 'error_code' (lido antes de ser "
        "atribuído; except KeyError não captura)",
        "caveat": "atributo inexistente, não None; subclasse de Exception",
    },
    {
        "id": "cps_pyserial_820",
        "repo": "pyserial/pyserial",
        "pr": 820,
        "merge": "b0b93cbd0ca735050c812057c4c29beb4573fc0e",
        "buggy": "9c7b6affe078b0f0b69efc05156b76f189d92e2d",
        "rebase": True,
        "source_file": "serial/serialposix.py",
        "function": "PosixPollSerial.read",
        "expression": "fd == self.pipe_abort_read_r",
        "crash": [],
        "expected_type": "UnboundLocalError",
        "kind": "excecao_local",
        "category": "variable_misuse",
        "source": "changed_line",
        "note": "UnboundLocalError: local variable 'fd' referenced before assignment (poll() devolve lista "
        "vazia no timeout)",
        "caveat": "PR integrado por rebase: a versão com bug é o commit anterior ao PR; select.poll e os.read "
        "precisam de stub nondet",
    },
    {
        "id": "cps_pyserial_149",
        "repo": "pyserial/pyserial",
        "pr": 149,
        "merge": "1eb040ee17cd82840cbbde1d6c763708e98c9adb",
        "buggy": "686abf500c419f11d0a4c07ac17628efeabd5693",
        "source_file": "serial/threaded/__init__.py",
        "function": "FramedPacket.data_received",
        "expression": "self.packet.append(byte)",
        "crash": [],
        "expected_type": "TypeError",
        "kind": "excecao_local",
        "category": "type_mismatch",
        "source": "changed_line",
        "note": "TypeError: 'bytes' object cannot be interpreted as an integer (serial.iterbytes devolve "
        "bytes de tamanho 1 no Python 3)",
    },
    {
        "id": "cps_pymavlink_1217",
        "repo": "ArduPilot/pymavlink",
        "pr": 1217,
        "merge": "56a3bb0c950ba0e0d2c50f2fadd74263fe6c3015",
        "buggy": "a2b74990d7f8f904564bca0bdc8f5f94a4263c3a",
        "source_file": "mavutil.py",
        "function": "add_message",
        "expression": "not mtype in messages",
        "crash": ["messages[mtype]._instances[instance_value] = msg"],
        "expected_type": "TypeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "TypeError: 'NoneType' object does not support item assignment (mensagem guardada antes sem "
        "instância deixa _instances None)",
        "caveat": "getattr com nome de campo variável e copy.copy",
    },
    {
        "id": "cps_mavproxy_1032",
        "repo": "ArduPilot/MAVProxy",
        "pr": 1032,
        "merge": "6403754f9b9cb935b4a071b90dc76856b0998b54",
        "buggy": "09dbeec3ed2fc382ee6abc4a2c63f971e206be58",
        "source_file": "MAVProxy/modules/mavproxy_fakegps.py",
        "function": "FakeGPSModule.idle_task",
        "expression": "now = time.time()",
        "crash": [_GPS_INPUT_SEND],
        "expected_type": "AttributeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "statement_after_insertion",
        "note": "AttributeError: 'NoneType' object has no attribute 'mav' (sem link com o veículo)",
    },
    {
        "id": "cps_mavproxy_881",
        "repo": "ArduPilot/MAVProxy",
        "pr": 881,
        "merge": "4616e6f1287bd8e04083410de030ef1f707366e6",
        "buggy": "df4249fdf0fadad39a8e5f30fe7573d0fea3d944",
        "source_file": "MAVProxy/modules/mavproxy_ftp.py",
        "function": "FTPModule.__init__ / FTPModule.check_read_send",
        "expression": "self.last_gap_send = None",
        "crash": ["now - self.last_gap_send"],
        "expected_type": "TypeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "TypeError: unsupported operand type(s) for -: 'float' and 'NoneType'",
        "caveat": "o bug nasce no __init__ e estoura em check_read_send; o harness monta o objeto",
    },
    {
        "id": "cps_dronekit_890",
        "repo": "dronekit/dronekit-python",
        "pr": 890,
        "merge": "e412e95d24169c606edcd87fa1dc309af305eb0e",
        "buggy": "a80a9bdbcfd7b80ba60a9fa860478cb748a4de16",
        "source_file": "dronekit/__init__.py",
        "function": "Vehicle.is_armable",
        "expression": "self.gps_0.fix_type > 1",
        "crash": [],
        "expected_type": "TypeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "TypeError: '>' not supported between instances of 'NoneType' and 'int' (GPS sem "
        "GPS_RAW_INT)",
    },
    {
        "id": "cps_blinka_434",
        "repo": "adafruit/Adafruit_Blinka",
        "pr": 434,
        "merge": "17b9bef0ecb286581464f4ec02a685dc98022b21",
        "buggy": "892ea29c1d1434f729e0404eac0ae2cf219b5c89",
        "source_file": "src/adafruit_blinka/microcontroller/bcm283x/pulseio/PWMOut.py",
        "function": "PWMOut.deinit",
        "expression": "self._pwmpin.stop()",
        "crash": [],
        "expected_type": "AttributeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "AttributeError: 'NoneType' object has no attribute 'stop' (deinit chamado duas vezes)",
        "caveat": "RPi.GPIO global precisa de stub",
    },
    {
        "id": "cps_opcua_1826",
        "repo": "FreeOpcUa/opcua-asyncio",
        "pr": 1826,
        "merge": "f12f3e19b3e7a3bc3db38add30176eef0cecd300",
        "buggy": "e3e02e3cfaca19647aec9348e9452594c6ebd657",
        "source_file": "asyncua/server/uaprocessor.py",
        "function": "UaProcessor._process_message",
        "expression": "self._connection.security_policy.peer_certificate + params.ClientNonce",
        "crash": [],
        "expected_type": "TypeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "TypeError: can't concat NoneType to bytes (CreateSession sem ClientNonce)",
        "caveat": ASYNC_NOTE + "; função enorme, recortar só o ramo CreateSession",
    },
    {
        "id": "cps_opcua_671",
        "repo": "FreeOpcUa/opcua-asyncio",
        "pr": 671,
        "merge": "49b611bdd2eb7eec569d72a981583afcfff7a657",
        "buggy": "fc09e423c7f3e49783b0788ad0933fd836175c15",
        "source_file": "asyncua/tools.py",
        "function": "application_to_strings",
        "expression": "app.DiscoveryUrls",
        "crash": [],
        "expected_type": "TypeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "TypeError: 'NoneType' object is not iterable (DiscoveryUrls None)",
    },
    {
        "id": "cps_ros2cli_1112",
        "repo": "ros2/ros2cli",
        "pr": 1112,
        "merge": "efae7a72e2be91e244fad11288aea55271173e77",
        "buggy": "5b182c67e4497d4a037b4dff5f4a7f2e9687b947",
        "source_file": "ros2cli/ros2cli/daemon/__init__.py",
        "function": "get_port",
        "expression": "int(os.environ.get('ROS_DOMAIN_ID', 0))",
        "crash": [],
        "expected_type": "ValueError",
        "kind": "excecao_local",
        "category": "type_mismatch",
        "source": "changed_line",
        "note": "ValueError: invalid literal for int() with base 10: '' (ROS_DOMAIN_ID vazia)",
    },
    {
        "id": "cps_ros2cli_1026",
        "repo": "ros2/ros2cli",
        "pr": 1026,
        "merge": "74f6989e71ed0376ff026d03a347acf2314d0c32",
        "buggy": "0a5b5603d9651c8b98e574142325069a04f31101",
        "source_file": "ros2doctor/ros2doctor/api/network.py",
        "function": "InterfaceFlags.__str__ / NetworkReport.report",
        "expression": "return",
        "crash": ["str(flags)"],
        "expected_type": "TypeError",
        "kind": "excecao_modelavel",
        "category": "type_mismatch",
        "source": "changed_line",
        "note": "TypeError: __str__ returned non-string (type NoneType), em str(flags) no relatório",
        "caveat": "incerto se o ESBMC-Python checa o tipo de retorno de __str__",
    },
    # Approved in docs/pgene601/cps_candidatos_extra_2026-10-12.md. Left out: scapy#5089 (the bug lives
    # in lambdas of a class body, no function to label) and dronekit#431 and #611 (the file uses
    # `await` as a variable name, which Python 3.7+ refuses to parse).
    {
        "id": "cps_pymodbus_2921",
        "repo": "pymodbus-dev/pymodbus",
        "pr": 2921,
        "merge": "5e0816c04b176932e10e49d7f8b8ae0817cde1e6",
        "buggy": "1b6c1400ab386bda4e9e70f16250492f531d40d0",
        "source_file": "pymodbus/framer/tls.py",
        "function": "FramerTLS.decode",
        "expression": "dev_id = int(data[6])",
        "crash": [],
        "expected_type": "IndexError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "statement_after_insertion",
        "note": "IndexError: index out of range (quadro Modbus/TLS com menos de 7 bytes)",
    },
    {
        "id": "cps_pymodbus_1738",
        "repo": "pymodbus-dev/pymodbus",
        "pr": 1738,
        "merge": "8de66a2cf046537cabe390f4dd0d57c3b127005c",
        "buggy": "85890dcbb6a0bf00f0b961a9dab420d348df2cae",
        "source_file": "pymodbus/mei_message.py",
        "function": "ReadDeviceInformationResponse.calculateRtuFrameSize",
        "expression": 'struct.unpack(">BB", buffer[size : size + 2])',
        "crash": [],
        "expected_type": "struct.error",
        "kind": "excecao_modelavel",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "struct.error: unpack requires a buffer of 2 bytes (quadro RTU parcial; o laço passa do "
        "fim do buffer)",
        "caveat": "classmethod; precisa do modelo de struct.unpack com fatia curta",
    },
    {
        "id": "cps_pymodbus_2977",
        "repo": "pymodbus-dev/pymodbus",
        "pr": 2977,
        "merge": "8a3be747ac72ab04797fd36eaa57d626abc6de14",
        "buggy": "60637425f44e716132970227be9280f1ccc808cc",
        "source_file": "pymodbus/pdu/register_message.py",
        "function": "WriteMultipleRegistersRequest.decode",
        "expression": 'struct.unpack(">H", data[idx : idx + 2])',
        "crash": [],
        "expected_type": "struct.error",
        "kind": "excecao_modelavel",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "struct.error: unpack requires a buffer of 2 bytes (quantidade declarada maior que o "
        "payload FC16)",
        "caveat": "o PR corrige o mesmo padrão em ReadWriteMultipleRegistersRequest.decode; só "
        "WriteMultipleRegistersRequest.decode está rotulada; precisa do modelo de struct.unpack",
    },
    {
        "id": "cps_minimqtt_5",
        "repo": "adafruit/Adafruit_CircuitPython_MiniMQTT",
        "pr": 5,
        "merge": "25b344ad65c2973efdfa637dc2b2a3e3d16873eb",
        "buggy": "801b3a3f0af52df20e96ef504db75e09960b0015",
        "source_file": "adafruit_minimqtt.py",
        "function": "MQTT.connect",
        "expression": "CONNACK_ERRORS[rc[3]]",
        "crash": [],
        "expected_type": "IndexError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "IndexError: index out of range (rc = self._sock.read(3) tem 3 bytes e o broker recusou "
        "a conexão)",
        "caveat": "só estoura com código de retorno diferente de 0; o socket precisa de stub",
    },
    {
        "id": "cps_umqtt_1149",
        "repo": "micropython/micropython-lib",
        "pr": 1149,
        "merge": "a7fe5c39f39bb52ae3e520ab5c1554c62dcddc29",
        "buggy": "ee4bb8ff139e24c42b739935fbd8ec7c4d061e02",
        "rebase": True,
        "source_file": "micropython/umqtt.simple/umqtt/simple.py",
        "function": "MQTTClient.connect",
        "expression": "resp[0] == 0x20 and resp[1] == 0x02",
        "crash": ["resp[3]"],
        "expected_type": "IndexError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "IndexError: index out of range (CONNACK com menos de 4 bytes; TypeError se o read "
        "devolver None no timeout)",
        "caveat": "PR integrado por rebase: o pai do merge já é o primeiro commit do PR, então a versão com "
        "bug é o commit anterior ao PR; o socket precisa de stub",
    },
    {
        "id": "cps_pyrtcm_34",
        "repo": "semuconsulting/pyrtcm",
        "pr": 34,
        "merge": "36fae9136fa3c6af872d2ef2639300c506d5635f",
        "buggy": "69207f298fe4cc719dbff11942856eaa988044d1",
        "source_file": "src/pyrtcm/rtcmmessage.py",
        "function": "RTCMMessage.__str__",
        "expression": "RTCM_MSGIDS[self.identity]",
        "crash": [],
        "expected_type": "KeyError",
        "kind": "excecao_local",
        "category": "invalid_precondition",
        "source": "changed_line",
        "note": "KeyError: identidade de mensagem RTCM3 não definida em RTCM_MSGIDS (com labelmsm ligado)",
        "caveat": "__str__ percorre self.__dict__; o harness recorta só o teste do dicionário",
    },
    {
        "id": "cps_pycomm3_331",
        "repo": "ottowayi/pycomm3",
        "pr": 331,
        "merge": "a466f887f7e53d410aa856065bf5ba8ef3ded479",
        "buggy": "d0d75601b27fff490b61c0f329387e79553210e3",
        "source_file": "pycomm3/cip/pccc.py",
        "function": "PCCCStringType._slc_string_swap",
        "expression": "[(x2, x1) for x1, x2 in (data[i : i + 2] for i in range(0, len(data), 2))]",
        "crash": [],
        "expected_type": "ValueError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "ValueError: not enough values to unpack (expected 2, got 1) (string SLC de comprimento "
        "ímpar)",
        "caveat": "patch grande (reescreve também os _encode e _decode do arquivo); a função rotulada tem "
        "4 linhas e usa itertools.chain",
    },
    {
        "id": "cps_udsoncan_291",
        "repo": "pylessard/python-udsoncan",
        "pr": 291,
        "merge": "48fabc495a737e1ef22ed0ffe59883b5c913eb19",
        "buggy": "976b197ed4359a8cce0ef3cdfc1b46afe7c55987",
        "source_file": "udsoncan/common/DidCodec.py",
        "function": "AsciiCodec.decode",
        "expression": "string_bin.decode('ascii')",
        "crash": [],
        "expected_type": "UnicodeDecodeError",
        "kind": "excecao_modelavel",
        "category": "invalid_precondition",
        "source": "changed_line",
        "note": "UnicodeDecodeError: 'ascii' codec can't decode byte 0xff (VIN não ASCII devolvido pela "
        "ECU)",
        "caveat": "depende de bytes.decode levantar erro no modelo do ESBMC, o que é incerto",
    },
    {
        "id": "cps_udsoncan_198",
        "repo": "pylessard/python-udsoncan",
        "pr": 198,
        "merge": "18027a94c2d5e086c9d5adeb125be8a60f5fb3ee",
        "buggy": "fda7a4221342b30fb53c0627dfa66335165977d5",
        "source_file": "udsoncan/client.py",
        "function": "Client.send_request",
        "expression": "timeout_type_used == 'single_request'",
        "crash": ["timeout_name_to_report"],
        "expected_type": "UnboundLocalError",
        "kind": "excecao_local",
        "category": "variable_misuse",
        "source": "statement_after_insertion",
        "note": "UnboundLocalError: local variable 'timeout_name_to_report' referenced before assignment "
        "(wait_frame devolve None sem TimeoutException)",
        "caveat": "função enorme; a expressão é o if que só atribui timeout_name_to_report dentro do "
        "except TimeoutException, e o patch passa esse if para depois do teste de recv_payload None; "
        "o harness recorta o laço de espera com recv_payload Optional",
    },
    {
        "id": "cps_gps_127",
        "repo": "adafruit/Adafruit_CircuitPython_GPS",
        "pr": 127,
        "merge": "c7c8d346f8efd60c18999ddd08b535e6b2aef963",
        "buggy": "3408f293e6f25ca55afb0bd24314deeff923fe69",
        "source_file": "adafruit_gps.py",
        "function": "_parse_degrees",
        "expression": "raw[1]",
        "crash": [],
        "expected_type": "IndexError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "IndexError: list index out of range (campo NMEA de grau sem ponto decimal; ValueError "
        "em int(raw[0]) se o campo for vazio)",
        "caveat": "patch grande porque cria o helper _split_decimal e mexe em outras funções; a versão "
        "com bug já inclui a correção de GPS#126 (primeiro pai do merge)",
    },
    {
        "id": "cps_gps_126",
        "repo": "adafruit/Adafruit_CircuitPython_GPS",
        "pr": 126,
        "merge": "3408f293e6f25ca55afb0bd24314deeff923fe69",
        "buggy": "c326d99d18513e3d45875f8ff6e11fd1b6765c70",
        "source_file": "adafruit_gps.py",
        "function": "GPS._update_timestamp_utc",
        "expression": "int(time_utc[0:2])",
        "crash": [],
        "expected_type": "ValueError",
        "kind": "excecao_local",
        "category": "type_mismatch",
        "source": "changed_line",
        "note": "ValueError: invalid literal for int() with base 10: '' (campo de hora NMEA vazio ou "
        "truncado; o mesmo vale para date)",
        "caveat": "time.struct_time no fim da função precisa de stub",
    },
    {
        "id": "cps_gps_60",
        "repo": "adafruit/Adafruit_CircuitPython_GPS",
        "pr": 60,
        "merge": "cc4c9dffc79df6ef6aa9c5df134b12cd811d574a",
        "buggy": "6fa737e2de914071271c8ec5670d96969ee7fe8a",
        "source_file": "adafruit_gps.py",
        "function": "GPS.update / _parse_talker",
        "expression": 'data_type = bytes(data_type.upper(), "ascii")',
        "crash": ["data_type[0]"],
        "expected_type": "IndexError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "statement_after_insertion",
        "note": "IndexError: index out of range em _parse_talker (sentença NMEA com tipo vazio)",
        "caveat": "a exceção nasce em _parse_talker, chamada por update; o harness liga as duas",
    },
    {
        "id": "cps_pythoncan_713",
        "repo": "hardbyte/python-can",
        "pr": 713,
        "merge": "216ed73d3250b1622dde62a7a2fbbffbfe320880",
        "buggy": "c93a2e0d2a6a43c8fa2e7ccf3ead1a0f0dc3dd8a",
        "source_file": "can/io/canutils.py",
        "function": "CanutilsLogReader.__iter__",
        "expression": "dlc = 0",
        "crash": ["dataBin"],
        "expected_type": "UnboundLocalError",
        "kind": "excecao_local",
        "category": "variable_misuse",
        "source": "statement_before_insertion",
        "note": "UnboundLocalError: local variable 'dataBin' referenced before assignment (quadro remoto "
        "antes de qualquer quadro de dados no log candump)",
        "caveat": "__iter__ é gerador; o patch insere dataBin = None no fim do ramo de quadro remoto, "
        "longe da linha que estoura",
    },
    {
        "id": "cps_pythoncan_225",
        "repo": "hardbyte/python-can",
        "pr": 225,
        "merge": "0d2707361337d1ca6c1b8a278a522f737742d9a7",
        "buggy": "b577d5e939c7bf04ef1c11b379e1a472e9809cc9",
        "source_file": "can/io/asc.py",
        "function": "ASCReader.__iter__",
        "expression": "(timestamp, channel, dummy) = temp.split(None, 2)",
        "crash": [],
        "expected_type": "ValueError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "ValueError: not enough values to unpack (expected 3, got 2) (linha do .asc com menos "
        "de três campos)",
        "caveat": "__iter__ é gerador; o PR também muda ASCWriter.log_event, que não está rotulado",
    },
    {
        "id": "cps_pymavlink_1058",
        "repo": "ArduPilot/pymavlink",
        "pr": 1058,
        "merge": "6929b9f7a8e121d4999c1eca8b845bf2f73a27d1",
        "buggy": "b6616bd5e183cfa08711b171d6aafaab0101e09b",
        "source_file": "DFReader.py",
        "function": "DFReader_binary.init_arrays_fast",
        "expression": "self.name_to_id['UNIT']",
        "crash": [],
        "expected_type": "KeyError",
        "kind": "excecao_local",
        "category": "invalid_precondition",
        "source": "changed_line",
        "note": "KeyError: 'UNIT' (log .BIN sem mensagem UNIT; o mesmo vale para MULT e FMTU)",
        "caveat": "mesma função de cps_pymavlink_1259, com outro bug; o patch é quase todo reindentação "
        "e o harness recorta só o bloco UNIT",
    },
    {
        "id": "cps_mavproxy_989",
        "repo": "ArduPilot/MAVProxy",
        "pr": 989,
        "merge": "b228d033284074b7fecd2b1b951d178e3f9f0138",
        "buggy": "a708305241005c934bf6843d6bddeeb60a4c3b0d",
        "source_file": "MAVProxy/modules/mavproxy_log.py",
        "function": "LogModule.log_status",
        "expression": "pct = 0",
        "crash": ["(100.0*file_size)/size"],
        "expected_type": "ZeroDivisionError",
        "kind": "excecao_local",
        "category": "division_by_zero",
        "source": "statement_before_insertion",
        "note": "ZeroDivisionError: float division by zero (LOG_ENTRY de log vazio, m.size == 0)",
        "caveat": "mesma função de cps_mavproxy_741, em outra versão; o patch insere um elif antes do "
        "else que divide",
    },
    {
        "id": "cps_mavproxy_741",
        "repo": "ArduPilot/MAVProxy",
        "pr": 741,
        "merge": "122a10c622a5ab86a2257d601ae54932eb24331f",
        "buggy": "33367bb2f9d9805de4946e7cb04931dffa7a653d",
        "source_file": "MAVProxy/modules/mavproxy_log.py",
        "function": "LogModule.log_status",
        "expression": "max(self.download_set)",
        "crash": [],
        "expected_type": "ValueError",
        "kind": "excecao_local",
        "category": "invalid_precondition",
        "source": "changed_line",
        "note": "ValueError: max() arg is an empty sequence (nenhum bloco do log chegou ainda)",
        "caveat": "mesma função de cps_mavproxy_989, em outra versão; os.path.getsize precisa de stub",
    },
    {
        "id": "cps_piouart_6",
        "repo": "adafruit/Adafruit_CircuitPython_PIO_UART",
        "pr": 6,
        "merge": "66046da48cfb4cdb6d5128b01d56c275d8beb3ac",
        "buggy": "fa6496a4dc2d66493402cf6f52707901317b4df3",
        "source_file": "adafruit_pio_uart.py",
        "function": "UART.read",
        "expression": "n == 0",
        "crash": ["n < len(buf)"],
        "expected_type": "TypeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "TypeError: '<' not supported between instances of 'NoneType' and 'int' (readinto "
        "devolve None com timeout 0)",
        "caveat": "readinto vira stub que devolve Optional[int]",
    },
    {
        "id": "cps_mavproxy_1572",
        "repo": "ArduPilot/MAVProxy",
        "pr": 1572,
        "merge": "cfa6203f59b80b9a7cf4f7a527a56ebd624542cb",
        "buggy": "b9c4a973be54e9cdffc52cc5ee09f695c463f857",
        "source_file": "MAVProxy/modules/mavproxy_ftp.py",
        "function": "FTPModule.send",
        "expression": "self.master.mav.file_transfer_protocol_send(self.network, self.target_system, "
        "self.target_component, payload)",
        "crash": [],
        "expected_type": "AttributeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "statement_after_insertion",
        "note": "AttributeError: 'NoneType' object has no attribute 'mav' (sem link com o veículo)",
        "caveat": "mesmo padrão de cps_mavproxy_1032",
    },
    {
        "id": "cps_mavproxy_1447",
        "repo": "ArduPilot/MAVProxy",
        "pr": 1447,
        "merge": "b344a7a3c1ce2ef0c8650a481d300b84253bedef",
        "buggy": "eb7f22be12d43dc331ea4f9673f2dc8a2d2043e0",
        "source_file": "MAVProxy/modules/mavproxy_battery.py",
        "function": "BatteryModule.cmd_bat",
        "expression": "self.battery_level[0]",
        "crash": [],
        "expected_type": "KeyError",
        "kind": "excecao_local",
        "category": "invalid_precondition",
        "source": "statement_after_insertion",
        "note": "KeyError: 0 (comando bat antes de chegar qualquer BATTERY_STATUS)",
    },
    {
        "id": "cps_gpiozero_716",
        "repo": "gpiozero/gpiozero",
        "pr": 716,
        "merge": "870f0513dad626e52432922b183250398ff9229d",
        "buggy": "f05efa993e1b8a2c130e785e352e913f6fdada86",
        "source_file": "gpiozero/other_devices.py",
        "function": "CPUTemperature.__init__ / CPUTemperature.value",
        "expression": "self.min_temp = min_temp",
        "crash": ["(self.temperature - self.min_temp) / temp_range"],
        "expected_type": "ZeroDivisionError",
        "kind": "excecao_local",
        "category": "division_by_zero",
        "source": "statement_after_insertion",
        "note": "ZeroDivisionError: float division by zero (min_temp == max_temp na configuração)",
        "caveat": "a correção fica no __init__ e o estouro na property value; a leitura do sensor "
        "(temperature) vira nondet",
    },
    {
        "id": "cps_simpleio_43",
        "repo": "adafruit/Adafruit_CircuitPython_SimpleIO",
        "pr": 43,
        "merge": "d1ea1bb923308fe17558521717b7c5700e355703",
        "buggy": "ecbd27a0992a840879d3d1c3e8730aa726087788",
        "source_file": "simpleio.py",
        "function": "map_range",
        "expression": "(x-in_min) * (out_max - out_min) / (in_max-in_min) + out_min",
        "crash": [],
        "expected_type": "ZeroDivisionError",
        "kind": "excecao_local",
        "category": "division_by_zero",
        "source": "changed_line",
        "note": "ZeroDivisionError: division by zero (faixa de entrada degenerada, in_min == in_max)",
    },
    {
        "id": "cps_pyspartn_4",
        "repo": "semuconsulting/pyspartn",
        "pr": 4,
        "merge": "76d2092c8ae3001fc3acee7ad03948e5dc750603",
        "buggy": "31cd509d163fb4da7065d22f0b4f93539450c48c",
        "source_file": "pyspartn/spartnmessage.py",
        "function": "SPARTNMessage.__init__",
        "expression": "bytes.fromhex(key)",
        "crash": [],
        "expected_type": "TypeError",
        "kind": "excecao_modelavel",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "TypeError: fromhex() argument must be str, not None (MQTTKEY não definida e sem key)",
        "caveat": "os.getenv vira parâmetro Optional[str]; depende do modelo de bytes.fromhex; o PR "
        "também muda spartnreader.py, que não está rotulado",
    },
    {
        "id": "cps_mavproxy_1380",
        "repo": "ArduPilot/MAVProxy",
        "pr": 1380,
        "merge": "0a44e1790042e3b14c227b369dbeb89253e8e2bd",
        "buggy": "92c01594173e029ce2334fed55a29757c2d50e59",
        "source_file": "MAVProxy/modules/mavproxy_map/mp_slipmap_ui.py",
        "function": "MPSlipMapPanel.click_position_text",
        "expression": 'terrain_height == "?"',
        "crash": ["terrain_height - self.last_terrain_height"],
        "expected_type": "TypeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "TypeError: unsupported operand type(s) for -: 'NoneType' and 'float' (mapa de "
        "elevação sem dado no ponto clicado)",
        "caveat": "arquivo de interface wx; mp_util e o mapa de elevação precisam de stub",
    },
    {
        "id": "cps_ros2cli_370",
        "repo": "ros2/ros2cli",
        "pr": 370,
        "merge": "096de53ba6f9424c8999a8a05821fdca17123585",
        "buggy": "ae2c0445146d4704e1eb692ee15c7313536e50f5",
        "source_file": "ros2doctor/ros2doctor/api/network.py",
        "function": "_check_network_config_helper",
        "expression": "iface.get('flags').lower()",
        "crash": [],
        "expected_type": "AttributeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "changed_line",
        "note": "AttributeError: 'NoneType' object has no attribute 'lower' (interface de rede sem flags)",
        "caveat": "a função ignora o parâmetro e chama ifcfg.interfaces(), que precisa de stub",
    },
    {
        "id": "cps_ros2cli_646",
        "repo": "ros2/ros2cli",
        "pr": 646,
        "merge": "a9def450ab9fed95d40b8bddd358cc06442192a4",
        "buggy": "737574d3a45ad615564c302bdf2bd09310fef61c",
        "source_file": "ros2param/ros2param/verb/list.py",
        "function": "ListVerb.main",
        "expression": "response = future.result()",
        "crash": ["response.result.names"],
        "expected_type": "AttributeError",
        "kind": "excecao_local",
        "category": "none_misuse",
        "source": "statement_after_insertion",
        "note": "AttributeError: 'NoneType' object has no attribute 'result' (serviço de parâmetros "
        "sem resposta dentro do timeout)",
        "caveat": "main usa rclpy; o harness recorta o laço de impressão com future.result() Optional",
    },
    {
        "id": "cps_paho_118",
        "repo": "eclipse-paho/paho.mqtt.python",
        "pr": 118,
        "merge": "dcd9dba86afeecb62453d34127d2e74f113a4af6",
        "buggy": "0618f61a88ff388a5bc9b1cc6bfcad0391491649",
        "source_file": "src/paho/mqtt/client.py",
        "function": "Client._host_matches_cert",
        "expression": 'host.split(".", 1)[1]',
        "crash": [],
        "expected_type": "IndexError",
        "kind": "excecao_local",
        "category": "out_of_bounds",
        "source": "changed_line",
        "note": "IndexError: list index out of range (hostname sem ponto e certificado curinga)",
    },
]


def _excerpt(source: str, qualified: str) -> str:
    """Each labelled function as it stands in the file; methods share one bare class header."""
    tree = ast.parse(source)
    lines = source.splitlines()
    groups: dict[str, list[str]] = {}
    for name in (n.strip() for n in qualified.split(" / ")):
        node = _one_function(tree, name)
        first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        body = lines[first - 1 : node.end_lineno]
        owner = name.split(".")[0] if "." in name else ""
        indent = "    " if owner else ""
        groups.setdefault(owner, []).append(
            "\n".join(
                indent + line[node.col_offset :] if line.strip() else ""
                for line in body
            )
        )
    parts = [
        (f"class {owner}:\n" if owner else "") + "\n\n".join(methods)
        for owner, methods in groups.items()
    ]
    return "\n\n\n".join(parts) + "\n"


def _grounded(source: str, qualified: str, expression: str) -> list[ast.AST]:
    tree = ast.parse(source)
    return [
        n
        for name in qualified.split(" / ")
        for n in expression_nodes(_one_function(tree, name.strip()), expression)
    ]


def _patch_touch(buggy: str, fixed: str, nodes: list[ast.AST]) -> tuple[str, int]:
    """Whether the fix rewrites a buggy line holding the expression, or inserts right next to it,
    and the line of the occurrence it touches (an expression can occur more than once)."""
    matcher = difflib.SequenceMatcher(
        None, buggy.splitlines(), fixed.splitlines(), autojunk=False
    )
    rewritten, inserted_before = set(), set()
    for tag, i1, i2, _, _ in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            rewritten.update(range(i1 + 1, i2 + 1))
        elif tag == "insert":
            inserted_before.update({i1, i1 + 1})
    for tag, near in (
        ("linha_alterada", lambda ls: ls & rewritten),
        ("insercao_adjacente", lambda ls: (ls | {x - 1 for x in ls}) & inserted_before),
    ):
        hits = [n.lineno for n in nodes if near(set(range(n.lineno, n.end_lineno + 1)))]
        if hits:
            return tag, min(hits)
    return "nao_tocada", min(n.lineno for n in nodes)


def build() -> list[str]:
    for sub in FOLDERS:
        (TARGET / sub).mkdir(parents=True, exist_ok=True)
        for path in (TARGET / sub).glob("cps_*"):
            path.unlink()
    report, truths, manifest = [], [], []
    for spec in SPECS:
        key, repo_url = spec["id"], f"https://github.com/{spec['repo']}"
        buggy_sha = spec["buggy"]
        buggy = _download(_raw_url(repo_url, buggy_sha, spec["source_file"]))
        fixed = _download(_raw_url(repo_url, spec["merge"], spec["source_file"]))
        if buggy is None or fixed is None or _function(buggy, spec["function"]) is None:
            raise SystemExit(f"{key}: could not fetch or locate {spec['function']}")
        cut = _excerpt(buggy, spec["function"])
        nodes = _grounded(buggy, spec["function"], spec["expression"])
        crash_ok = all(_grounded(buggy, spec["function"], c) for c in spec["crash"])
        if (
            not nodes
            or not _grounded(cut, spec["function"], spec["expression"])
            or not crash_ok
        ):
            raise SystemExit(
                f"{key}: expression or crash site not in the buggy function"
            )
        touch, line = _patch_touch(buggy, fixed, nodes)
        if touch == "nao_tocada":
            raise SystemExit(f"{key}: the fix does not touch the labelled expression")
        report.append(
            f"{key:22s} grounded={len(nodes)} crash_ok={crash_ok} patch={touch} ({spec['source']})"
        )
        name = f"{key}.py"
        (TARGET / "funcao_com_bug" / name).write_text(cut, encoding="utf-8")
        (TARGET / "arquivo_com_bug" / name).write_text(buggy, encoding="utf-8")
        (TARGET / "arquivo_corrigido" / name).write_text(fixed, encoding="utf-8")
        patch = difflib.unified_diff(
            buggy.splitlines(keepends=True),
            fixed.splitlines(keepends=True),
            f"a/{spec['source_file']}",
            f"b/{spec['source_file']}",
        )
        (TARGET / "patches" / f"{key}.diff").write_text(
            "".join(patch), encoding="utf-8"
        )
        item = {
            "id": key,
            "cohort": COHORT,
            "function": spec["function"],
            "expression": spec["expression"],
            "categories": [spec["category"]],
            "line": line,
            "label_sources": {"expression": spec["source"], "category": "patch_lido"},
            "review": "patch_lido",
            "provenance": {
                "project": spec["repo"].split("/")[1],
                "repo_url": repo_url,
                "pr_url": f"{repo_url}/pull/{spec['pr']}",
                "source_file": spec["source_file"],
                "source_function": spec["function"],
                "buggy_commit": buggy_sha,
                "fixed_commit": spec["merge"],
                "buggy_commit_rule": "commit anterior ao PR (merge por rebase)"
                if spec.get("rebase")
                else "primeiro pai do merge",
            },
            "expected_type": spec["expected_type"],
            "failure_kind": spec["kind"],
            "failure_kind_source": "patch_lido",
            "failure_kind_note": spec["note"],
        }
        if spec["crash"]:
            item["crash_expressions"] = spec["crash"]
        if spec.get("caveat"):
            item["ressalva"] = spec["caveat"]
        truths.append({**item, "file": name})
        manifest.append({**item, "detection_file": f"funcao_com_bug/{name}"})
    policy = {
        "detection_scope": "only items not requiring patch context",
        "patch_context_items": [],
    }
    description = (
        f"Dataset da disciplina PGENE601: {len(SPECS)} bugs de execução corrigidos em PRs aceitos de projetos "
        "Python ciber-físicos. Separado de dataset/bugs_reais e da dissertação."
    )
    documents = {
        "ground_truths.json": truths,
        "manifest.json": manifest,
        "manifest_full.json": [
            {**m, "detection_file": f"arquivo_com_bug/{m['id']}.py"} for m in manifest
        ],
    }
    for filename, items in documents.items():
        payload = {
            "evaluation_policy": policy,
            "description": description,
            "items": items,
        }
        (TARGET / filename).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return report


if __name__ == "__main__":
    print("\n".join(build()))
