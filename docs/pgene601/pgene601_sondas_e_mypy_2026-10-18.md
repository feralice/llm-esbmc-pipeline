# PGENE601: sondas do ESBMC e linha de base do mypy (18/10/2026)

Trabalho sem LLM, para não competir com a rodada final da dissertação pela assinatura do Claude.
Corpus: `dataset/disciplina_pgene601/` (47 bugs). ESBMC v8.6 (`~/esbmc-releases/v8.6/esbmc.sh`).

## Sondas de bytes no ESBMC v8.6

Programas em `artifacts/pgene601/sondas-2026-10-18/`, `--unwind 5`.

| Sonda | CPython | ESBMC v8.6 |
|---|---|---|
| `struct.unpack(">BB", data[0:2])` com 1 byte | `struct.error` | recusa: `Could not resolve type of receiver in member call '.struct.unpack()'` |
| o mesmo com 2 bytes (caso válido) | roda | recusa igual: `struct.unpack` não é aceito em nenhum caso |
| `nondet_bytes(n)` com `n` simbólico | (entrada) | recusa: `nondet_bytes(n) requires a constant integer length` |
| `b"\xff\xfe".decode("utf-8")` | `UnicodeDecodeError` | **VERIFICATION SUCCESSFUL** (falso negativo) |
| `bytes.fromhex(s)` com `s` vindo de um ramo | `ValueError` | recusa: `bytes.fromhex() is only supported on a constant string` |

Consequências para o corpus:
- os itens com `struct.unpack` (cps_pymodbus_2980, 2977, 1738, cps_pymavlink_1259, 1058) não chegam ao
  ESBMC sem um stub de `struct.unpack` com a semântica do tamanho (`struct.error` quando
  `len(buf) != calcsize(fmt)`; com `fmt` constante, o tamanho sai na montagem do harness);
- o harness hoje dá a um parâmetro `bytes` só dois valores (`b"ab"` ou `b""`, `render.py`), e o ESBMC não
  aceita comprimento simbólico; para pacotes curtos, a saída é escolher entre alguns comprimentos
  constantes (`nondet_bytes(0)` a `nondet_bytes(k)` por `nondet_bool()`);
- `bytes.decode` dá falso negativo: o replay no CPython continua decisivo (cps_pycomm3_331,
  cps_udsoncan_291);
- `bytes.fromhex` só com texto constante (cps_pyspartn_4).
Material para issue ao Lucas, junto com os reprodutores do piloto.

## mypy como linha de base

Comando: `.venv/bin/python scripts/pgene601_mypy_baseline.py dataset/disciplina_pgene601 <saida.json>`
(mypy 2.1.0, `--ignore-missing-imports --follow-imports=skip`, com e sem `--check-untyped-defs`). Conta
como acerto um erro do mypy na linha do gabarito ou numa linha de `crash_expressions` da versão com bug.
Resultado em `artifacts/pgene601/mypy-2026-10-18/mypy_cps.json`.

- Padrão: acerta 2 de 47 (cps_pythoncan_1293, cps_gps_127).
- `--check-untyped-defs`: acerta 5 de 47, mas só 3 com a mensagem certa para o bug:
  - **cps_pyspartn_4**: `Argument 1 to "fromhex" ... "Any | None"; expected "str"`; some na versão corrigida;
  - **cps_mavproxy_881**: `Unsupported operand types for - ("float" and "None")`; a mesma mensagem continua
    na versão corrigida;
  - **cps_blinka_434**: `Item "None" ... has no attribute "stop"`; continua na versão corrigida.
  - cps_pythoncan_1293 (`Cannot determine type`) e cps_gps_127 (`float` em variável `int`, o bug é
    IndexError) não descrevem o bug.
- Ruído: 619 mensagens no total, em 36 dos 47 arquivos (mediana de 4 por arquivo).

Leitura: o mypy aponta o bug com a mensagem certa em 3 de 47, e só em 1 a mensagem some na correção.
Nos 17 itens de None, onde se esperava mais, ele quase não ajuda: sem anotação o valor é `Any`, e o
mypy não sabe que o atributo pode ser None.

## Sondas refeitas no master (27/10/2026)

Mesmos cinco programas, `--unwind 5 --no-pointer-check --no-align-check`, em dois binários: master limpo
`7da3564` (`~/.local/bin/esbmc-7da3564`, 22/10) e `build-bw` compilado em 27/10 sobre `c42f28b671`, que sai
"dirty tree" por 177 linhas de patch local no frontend Python. Resultado idêntico nos dois e igual ao da v8.6:
`struct.unpack` recusado (com 1 e com 2 bytes), `nondet_bytes(n)` exige tamanho constante, `bytes.fromhex`
só com texto constante, e `b"\xff\xfe".decode("utf-8")` continua SUCCESSFUL (falso negativo). Busca no
GitHub (`struct.unpack`, `nondet_bytes`, `decode UnicodeDecodeError`, `fromhex`) não achou issue aberta sobre
nenhum dos cinco: são candidatos a issue, a abrir só com aprovação dela.
