"""Build dataset/disciplina_pgene601/adafruit_valor/: four wrong-value bugs in Adafruit CircuitPython sensor
drivers, each with a datasheet property, to test the PGENE601 hypothesis that a datasheet range works as the
verification property.

Same layout as the parent folder. These bugs raise no exception, so each item carries a `datasheet` block:
the precondition that keeps the reading physically valid and the postcondition the driver must meet, both
over the raw register bytes, plus the datasheet source. Rerunning rebuilds the folder.

Left out: MCP9808#5 (sign bit read backwards), because `MCP9808.temperature` has a getter and a setter
of the same name, and neither this builder nor the pipeline's grounding can tell which one is meant.
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_disciplina_pgene601 import (
    _download,
    _excerpt,
    _function,
    _grounded,
    _patch_touch,
    _raw_url,
)

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dataset" / "disciplina_pgene601" / "adafruit_valor"
COHORT = "disciplina_pgene601_adafruit"
FOLDERS = ("funcao_com_bug", "arquivo_com_bug", "arquivo_corrigido", "patches")

SPECS = [
    {
        "id": "ada_shtc3_5",
        "repo": "adafruit/Adafruit_CircuitPython_SHTC3",
        "pr": 5,
        "merge": "9ecdce67f4ac76925fdd11a1cf981a4e72736d95",
        "buggy": "8e0fea8535ee843c39d7477a954cff60657ffea9",
        "source_file": "adafruit_shtc3.py",
        "function": "SHTC3.measurements",
        "expression": 'raw_temp = unpack_from(">h", temp_data)[0]',
        "category": "type_mismatch",
        "note": "o valor cru de 16 bits é lido com sinal; acima de 42,5 °C a temperatura sai negativa (issue #4)",
        "datasheet": {
            "sensor": "Sensirion SHTC3",
            "requirement": "faixa de medição de temperatura de -40 a 125 °C; T = -45 + 175 * S_T / 2^16, S_T sem sinal",
            "precondition": "o valor cru S_T = (b0 << 8) | b1 corresponde a uma temperatura dentro da faixa "
            "(1873 <= S_T <= 63663) e o CRC confere",
            "postcondition": "-40 <= temperature <= 125",
            "source": "https://sensirion.com/shtc3",
        },
    },
    {
        "id": "ada_max31855_11",
        "repo": "adafruit/Adafruit_CircuitPython_MAX31855",
        "pr": 11,
        "merge": "5f51a0250dece3ad1751426ca8be40dcea8b2228",
        "buggy": "a47c8f78f0de4cc443b775854e738540d8304b08",
        "source_file": "adafruit_max31855.py",
        "function": "MAX31855.reference_temperature",
        "expression": "return self._read(True) * 0.625",
        "category": "invalid_precondition",
        "note": "fator de conversão da junção fria dez vezes maior (0,625 em vez de 0,0625 °C por LSB) (issue #10)",
        "datasheet": {
            "sensor": "Maxim/Analog Devices MAX31855",
            "requirement": "resolução da temperatura da junção fria de 0,0625 °C; faixa de operação de -40 a 125 °C",
            "precondition": "o valor de 12 bits da junção fria corresponde a uma temperatura de operação válida "
            "(-640 <= refer <= 2000) e nenhum bit de falha está ligado",
            "postcondition": "-40 <= reference_temperature <= 125",
            "source": "https://wcm-cce.cldnet.analog.com/media/en/technical-documentation/data-sheets/MAX31855.pdf",
        },
    },
    {
        "id": "ada_tsl2591_6",
        "repo": "adafruit/Adafruit_CircuitPython_TSL2591",
        "pr": 6,
        "merge": "8a9647bcc4a34a438106a301c35c9773b3e46d10",
        "buggy": "0fa3c2e585821b8cbeba668e721a8e561ad79b7c",
        "source_file": "adafruit_tsl2591.py",
        "function": "TSL2591.lux",
        "expression": "if channel_0 == 0xFFFF or channel_1 == 0xFFFF:",
        "category": "invalid_precondition",
        "note": "com integração de 100 ms o canal satura em 36863, não em 65535; a saturação vira lux (issue #5)",
        "caveat": "a propriedade é sobre não devolver valor: com o canal saturado, lux deve levantar erro",
        "datasheet": {
            "sensor": "ams TSL2591",
            "requirement": "contagem máxima do ADC de 36863 com ATIME = 100 ms e 65535 nos demais tempos",
            "precondition": "canais de 16 bits (0 a 65535)",
            "postcondition": "se lux devolve um valor com integração de 100 ms, channel_0 < 36863 e channel_1 < 36863",
            "source": "https://web.physics.ucsb.edu/~phys126/lipman/handouts/datasheets/ams_tsl2591.pdf",
        },
    },
    {
        "id": "ada_tsl2591_34",
        "repo": "adafruit/Adafruit_CircuitPython_TSL2591",
        "pr": 34,
        "merge": "391dd858390b460296b74edd88c56020d9035fa6",
        "buggy": "573f035d8f1e6df6daad608ca9adee1961c599cd",
        "source_file": "adafruit_tsl2591.py",
        "function": "TSL2591.visible",
        "expression": "full = (channel_1 << 16) | channel_0",
        "category": "integer_overflow",
        "note": "luz visível montada como número de 32 bits juntando os dois canais; o valor sai na casa dos milhões",
        "caveat": "o PR corrige também full_spectrum, com o mesmo padrão; só visible está rotulada",
        "datasheet": {
            "sensor": "ams TSL2591",
            "requirement": "cada canal é um ADC de 16 bits; CH0 mede visível mais infravermelho e CH1 só infravermelho",
            "precondition": "canais de 16 bits com channel_1 <= channel_0",
            "postcondition": "0 <= visible <= 65535",
            "source": "https://web.physics.ucsb.edu/~phys126/lipman/handouts/datasheets/ams_tsl2591.pdf",
        },
    },
]


def build() -> list[str]:
    for sub in FOLDERS:
        (TARGET / sub).mkdir(parents=True, exist_ok=True)
        for path in (TARGET / sub).glob("ada_*"):
            path.unlink()
    report, truths, manifest = [], [], []
    for spec in SPECS:
        key, repo_url = spec["id"], f"https://github.com/{spec['repo']}"
        buggy = _download(_raw_url(repo_url, spec["buggy"], spec["source_file"]))
        fixed = _download(_raw_url(repo_url, spec["merge"], spec["source_file"]))
        if buggy is None or fixed is None or _function(buggy, spec["function"]) is None:
            raise SystemExit(f"{key}: could not fetch or locate {spec['function']}")
        cut = _excerpt(buggy, spec["function"])
        nodes = _grounded(buggy, spec["function"], spec["expression"])
        if not nodes or not _grounded(cut, spec["function"], spec["expression"]):
            raise SystemExit(f"{key}: expression not in the buggy function")
        touch, line = _patch_touch(buggy, fixed, nodes)
        if touch == "nao_tocada":
            raise SystemExit(f"{key}: the fix does not touch the labelled expression")
        report.append(f"{key:18s} grounded={len(nodes)} patch={touch} line={line}")
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
        (TARGET / "patches" / f"{key}.diff").write_text("".join(patch), encoding="utf-8")
        item = {
            "id": key,
            "cohort": COHORT,
            "function": spec["function"],
            "expression": spec["expression"],
            "categories": [spec["category"]],
            "line": line,
            "label_sources": {"expression": "changed_line", "category": "patch_lido"},
            "review": "patch_lido",
            "provenance": {
                "project": spec["repo"].split("/")[1],
                "repo_url": repo_url,
                "pr_url": f"{repo_url}/pull/{spec['pr']}",
                "source_file": spec["source_file"],
                "source_function": spec["function"],
                "buggy_commit": spec["buggy"],
                "fixed_commit": spec["merge"],
                "buggy_commit_rule": "primeiro pai do merge",
            },
            "expected_type": "resultado_errado",
            "failure_kind": "resultado_errado",
            "failure_kind_source": "patch_lido",
            "failure_kind_note": spec["note"],
            "datasheet": spec["datasheet"],
        }
        if spec.get("caveat"):
            item["ressalva"] = spec["caveat"]
        truths.append({**item, "file": name})
        manifest.append({**item, "detection_file": f"funcao_com_bug/{name}"})
    policy = {"detection_scope": "only items not requiring patch context", "patch_context_items": []}
    description = (
        f"Subconjunto da PGENE601: {len(SPECS)} bugs de valor errado em drivers de sensores da Adafruit, cada um "
        "com uma propriedade tirada do datasheet. Separado de dataset/bugs_reais e da dissertação."
    )
    documents = {
        "ground_truths.json": truths,
        "manifest.json": manifest,
        "manifest_full.json": [{**m, "detection_file": f"arquivo_com_bug/{m['id']}.py"} for m in manifest],
    }
    for filename, items in documents.items():
        payload = {"evaluation_policy": policy, "description": description, "items": items}
        (TARGET / filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print("\n".join(build()))
