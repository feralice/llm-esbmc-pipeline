# Issue aberta: adafruit/Adafruit_CircuitPython_GPS#132 (12/11/2026)

Repositório: adafruit/Adafruit_CircuitPython_GPS. Rótulo sugerido: `bug`.
Verificado no commit `c67a122` (igual a `origin/HEAD` em 12/11/2026). Sem issue ou PR sobre o tema na busca.

## Title

GSA with 17 fields drops the 12th satellite from `sat_prns`

## Body

In `_parse_gsa`, the satellite list is built with `data[2:-4]`:

```python
satlist = list(filter(None, data[2:-4]))
```

That slice is right for the 18-field GSA (the one with the system ID at index 17), where the satellites are indexes 2 to 13. For the 17-field GSA it is off by one: `data[2:-4]` on a 17-item list is `data[2:13]`, so index 13 (the 12th satellite) is dropped.

The driver itself fixes the layout: PDOP, HDOP and VDOP are read from indexes 14, 15 and 16, so the satellites must be at 2 to 13.

### Reproduction

A GSA sentence with 12 satellites and a valid checksum, parsed through `update()` with a fake UART:

```
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.5,1.2,0.9*<checksum calculado>
```

Result on `c67a122`: `sat_prns` has 11 entries, `GP12` is missing. The same sentence with a 18th field (system ID `1`) gives 12 entries.

### Expected

`sat_prns` contains all 12 satellites for both forms.

### Suggested fix

Slice up to the DOP fields instead of counting from the end, for example `data[2:14]`, which is correct for both lengths because the DOP indexes do not change.

## Notes for the author (not part of the issue)

- Only the 17-field form is affected. Receivers that send the 18-field GSA are not.
- No test for this case exists in the repository as far as I could see.
- Before opening: confirm on the current `main`, and re-check the search for existing issues.
