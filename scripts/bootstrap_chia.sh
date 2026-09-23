#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.10}"
EXPECTED="3.10.19"
CHIA_COMMIT="${CHIA_COMMIT:-16c35e92aaaf9511c6453bf94cd5cf589698f4e3}"
ACTUAL="$(${PYTHON_BIN} -c 'import platform; print(platform.python_version())' 2>/dev/null || true)"

if [[ "${ACTUAL}" != "${EXPECTED}" ]]; then
  echo "Expected Python ${EXPECTED} for the current upstream CHIA environment, found '${ACTUAL:-missing}'." >&2
  echo "Set PYTHON_BIN to an interpreter for Python ${EXPECTED}, then retry." >&2
  exit 2
fi

mkdir -p external
if [[ ! -d external/chia/.git ]]; then
  git clone --no-recurse-submodules https://github.com/ucb-bar/chia external/chia
fi

# Keep the upstream checkout reproducible while deliberately avoiding recursive
# submodule initialization. At the pinned CHIA revision, examples/benchmarks
# references an unavailable commit; CHIA core + Ray do not need that example
# submodule for Gate A.1.
git -C external/chia fetch origin "${CHIA_COMMIT}" --depth=1
git -C external/chia checkout --detach "${CHIA_COMMIT}"
git -C external/chia submodule deinit -f --all >/dev/null 2>&1 || true

${PYTHON_BIN} -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e external/chia
python -m pip install -e ".[test]"

python - <<'PY'
from chia.base.ChiaFunction import ChiaFunction, get  # noqa: F401
import ray

print("CHIA core imports: PASS")
print("Ray version:", ray.__version__)
PY

echo "Bootstrap complete. Pinned upstream CHIA commit: ${CHIA_COMMIT}"
echo "Submodules intentionally not initialized for Gate A.1."
echo "Next: python scripts/real_chia_smoke.py"
