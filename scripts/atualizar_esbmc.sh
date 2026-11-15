#!/usr/bin/env bash
# --check only reads metadata. Use --execute only after Fernanda authorizes the update.
set -euo pipefail
mode=${1:-}
if [[ $# -ne 1 || ( $mode != --check && $mode != --execute ) ]]; then
  echo 'Uso: bash scripts/atualizar_esbmc.sh --check | --execute (requer autorização)' >&2
  exit 2
fi
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
esbmc_root=${ESBMC_UPDATE_ROOT:-$HOME/esbmc-master}
build_dir=$esbmc_root/build-bw
binary=${ESBMC_UPDATE_BINARY:-$build_dir/src/esbmc/esbmc}
python_bin=${PIPELINE_PYTHON:-$project_root/.venv/bin/python}
export PYTHONPATH="$project_root/src${PYTHONPATH:+:$PYTHONPATH}"
read_provenance() {
  "$python_bin" -c 'import json,sys; from research_pipeline.verify.esbmc_provenance import esbmc_provenance; print(json.dumps(esbmc_provenance([sys.argv[1]]), ensure_ascii=False))' "$binary"
}
for solver in BITWUZLA Z3; do
  if ! grep -Eq "^ENABLE_${solver}:BOOL=(On|ON|TRUE|1)$" "$build_dir/CMakeCache.txt"; then
    echo "O cache de build-bw não confirma $solver ligado. Confira a configuração antes de atualizar." >&2
    exit 1
  fi
done
if [[ $mode == --check ]]; then
  read_provenance
  exit 0
fi
"$python_bin" - "$esbmc_root" <<'PYGUARD'
import sys
from pathlib import Path
from research_pipeline.verify.esbmc_provenance import check_update_checkout

try:
    check_update_checkout(Path(sys.argv[1]))
except ValueError as exc:
    print(exc, file=sys.stderr)
    raise SystemExit(1) from exc
PYGUARD
smoke_program=${ESBMC_SMOKE_PROGRAM:-$project_root/artifacts/pgene601/ajustes-2026-11-07/programs/e5d6b90703b8_a0.py}
if [[ ! -f $smoke_program ]]; then
  echo "Programa já confirmado de cps_simpleio_43 não encontrado: $smoke_program" >&2
  exit 1
fi
log_dir=$(mktemp -d "${TMPDIR:-/tmp}/llm-esbmc-update.XXXXXX")
echo "Logs da atualização: $log_dir"
smoke() {
  local phase=$1 code=0
  timeout 180 "$binary" --no-pointer-check --no-align-check --unwind 5 --multi-property \
    "$smoke_program" > "$log_dir/$phase.log" 2>&1 || code=$?
  if (( code == 124 || code >= 128 )) || ! grep -q 'VERIFICATION FAILED' "$log_dir/$phase.log" \
     || ! grep -q 'ZeroDivisionError' "$log_dir/$phase.log"; then
    echo "cps_simpleio_43 não manteve a confirmação ($phase). Pare e confira $log_dir/$phase.log" >&2
    exit 1
  fi
}
smoke before
# The cached configuration preserves the Python frontend, Bitwuzla, Z3 and the previous dependency paths.
git -C "$esbmc_root" pull --ff-only
ninja -C "$build_dir" esbmc
read_provenance > "$log_dir/provenance.json"
"$python_bin" -c 'import json,sys; from research_pipeline.verify.esbmc_provenance import check_fresh; check_fresh(json.load(open(sys.argv[1])))' "$log_dir/provenance.json"
smoke after
"$python_bin" -c 'import json,sys; from pathlib import Path; from research_pipeline.verify.esbmc_provenance import record_version; record_version(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]))' "$log_dir/provenance.json" "$project_root/docs/experimentos/ESBMC_VERSOES.md"
