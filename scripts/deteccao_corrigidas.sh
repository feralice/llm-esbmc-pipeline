#!/usr/bin/env bash
# Prepares paired fixed functions. Only --execute starts paid detection, after authorization.
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"
exec "${PIPELINE_PYTHON:-$project_root/.venv/bin/python}" scripts/preparar_deteccao_corrigidas.py "$@"
