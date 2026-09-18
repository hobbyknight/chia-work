#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.10}"
EXPECTED="3.10.19"
ACTUAL="$(${PYTHON_BIN} -c 'import platform; print(platform.python_version())' 2>/dev/null || true)"

if [[ "${ACTUAL}" != "${EXPECTED}" ]]; then
  echo "Expected Python ${EXPECTED} for the current upstream CHIA environment, found '${ACTUAL:-missing}'." >&2
  echo "Set PYTHON_BIN to an interpreter for Python ${EXPECTED}, then retry." >&2
  exit 2
fi

mkdir -p external
if [[ ! -d external/chia/.git ]]; then
  git clone https://github.com/ucb-bar/chia external/chia
else
  echo "external/chia already exists; not pulling automatically to preserve reproducibility."
fi

${PYTHON_BIN} -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e external/chia
python -m pip install -e .

python - <<'PY'
from chia.base.ChiaFunction import ChiaFunction  # noqa: F401
print("CHIA import: PASS")
PY

echo "Bootstrap complete. Record the external/chia commit before freezing experiments."
