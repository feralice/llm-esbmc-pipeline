# PGENE601: repositórios para o modo `scan` (19/10/2026)

Objetivo: além dos 47 bugs conhecidos e do subconjunto Adafruit, procurar bugs **novos** em software Python
ciber-físico com o modo `scan` (grafo de chamadas, detecção por função com os chamadores, motor verify).
Nada aqui chamou a LLM: o `scan` sem `--yes` só monta o grafo e a seleção e estima o custo.

## Medição

Clone raso de cada repositório em 19/10/2026, `--mode scan` sem `--yes`. "funções" é a seleção do `scan`;
"linhas", "struct" e "async" contam o código fora de testes, docs e exemplos ("struct" soma `struct.`,
`unpack(` e `unpack_from`, que o ESBMC v8.6 recusa, ver `pgene601_sondas_e_mypy_2026-10-18.md`);
"tokens" é a estimativa da detecção (a verificação gasta até 3 chamadas a mais por hipótese).

| repositório | ★ | último push | funções | linhas | struct | async | tokens |
|---|---|---|---|---|---|---|---|
| Knio/pynmea2 | 682 | 2026-04 | 90 | 3202 | 0 | 0 | 319 mil |
| adafruit/Adafruit_CircuitPython_GPS | 80 | 2026-09 | 41 | 944 | 0 | 0 | 154 mil |
| semuconsulting/pynmeagps | 112 | 2026-10 | 104 | 7665 | 1 | 0 | 382 mil |
| semuconsulting/pyrtcm | 116 | 2026-10 | 44 | 5144 | 0 | 0 | 161 mil |
| semuconsulting/pyubx2 | 257 | 2026-10 | 150 | 10287 | 4 | 0 | 553 mil |
| pyhys/minimalmodbus | 345 | 2024-04 | 71 | 4048 | 3 | 0 | 277 mil |
| adafruit/Adafruit_CircuitPython_BME280 | 66 | 2026-04 | 34 | 853 | 4 | 0 | 124 mil |
| adafruit/Adafruit_CircuitPython_LSM6DS | 34 | 2026-04 | 19 | 824 | 0 | 0 | 70 mil |
| ottowayi/pycomm3 | 520 | 2025-12 | 296 | 8693 | 3 | 0 | 1,09 mi |
| eclipse-paho/paho.mqtt.python | 2430 | 2026-10 | 298 | 6647 | 58 | 0 | 1,10 mi |
| pyserial/pyserial | 3587 | 2026-05 | 416 | 8351 | 32 | 0 | 1,52 mi |
| pylessard/python-udsoncan | 736 | 2026-09 | 391 | 10946 | 102 | 0 | 1,45 mi |
| cantools/cantools | 2303 | 2026-10 | 634 | 18812 | 27 | 0 | 2,40 mi |
| pymodbus-dev/pymodbus | 2784 | 2026-10 | 688 | 11407 | 143 | 87 | 2,52 mi |
| gijzelaerr/python-snap7 | 859 | 2026-10 | 700 | 18692 | 453 | 94 | 2,61 mi |
| gpiozero/gpiozero | 2141 | 2026-07 | 796 | 16134 | 12 | 0 | 2,86 mi |
| hardbyte/python-can | 1609 | 2026-07 | 817 | 27958 | 60 | 2 | 3,00 mi |
| ArduPilot/pymavlink | 738 | 2026-10 | 1136 | 33797 | 135 | 0 | 4,31 mi |
| ArduPilot/MAVProxy | 600 | 2026-10 | 4402 | 86105 | 219 | 0 | 16,3 mi |

## Escolha

Critérios: código que interpreta dado vindo do dispositivo; pouco `struct` e nenhum `async` (o ESBMC
recusa os dois); custo que caiba na assinatura; repositório ativo, para que um achado possa virar issue; e,
seguindo a caça de bugs de agosto, código de organização conhecida mas pouco auditado em vez de biblioteca
madura.

**Primeira leva (8 repositórios, cerca de 2 milhões de tokens na detecção):**
1. **Adafruit_CircuitPython_GPS**: parser de NMEA em driver pouco auditado; três bugs do corpus
   (cps_gps_60, 126, 127) vieram dele, então o código já mostrou que tem bug desse tipo.
2. **pynmea2**: parser de NMEA muito usado, só texto, sem `struct`.
3. **pynmeagps**, **pyrtcm** e **pyubx2**: parsers de GNSS (NMEA, RTCM3, UBX) da mesma autoria, ativos,
   quase sem `struct`.
4. **minimalmodbus**: Modbus RTU/ASCII num arquivo só, parado desde 2024 mas muito usado.
5. **Adafruit_CircuitPython_BME280** e **LSM6DS**: drivers de sensor pequenos com fórmulas de compensação;
   servem também para a hipótese do datasheet.

**Depois, com `--scan-limit`:** pycomm3, paho-mqtt, pyserial e cantools (1 a 2,4 milhões de tokens cada).

**Fora por agora:** pymodbus e python-snap7 (muito `struct` e `async`), udsoncan e pymavlink (muito
`struct`), python-can e gpiozero (grandes, e o achado provável é em código de plataforma), MAVProxy
(16 milhões de tokens).

## Como rodar (depois da rodada final da dissertação)

```bash
PYTHONPATH=src .venv/bin/python src/main.py --mode scan --input <clone> \
  --backend claude_cli --model claude-sonnet-5-5 --synth-backend claude_cli --synth-model claude-sonnet-5-5 \
  --esbmc-command ~/esbmc-releases/v8.6/esbmc.sh --output-dir artifacts/pgene601/scan-<repo> --yes
```

Um repositório por vez, começando pelo Adafruit_CircuitPython_GPS (o menor e o mais provável). Todo
CONFIRMED passa por leitura manual antes de virar issue: sem gabarito, um achado só vale se o contexto de
chamada real permitir a entrada que o ESBMC usou.
