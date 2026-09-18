#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Run: bash scripts/bootstrap_chia.sh" >&2
  exit 2
fi

# shellcheck disable=SC1091
source .venv/bin/activate

EXPECTED_PYTHON="3.10.19"
ACTUAL_PYTHON="$(python -c 'import platform; print(platform.python_version())')"
if [[ "${ACTUAL_PYTHON}" != "${EXPECTED_PYTHON}" ]]; then
  echo "Expected Python ${EXPECTED_PYTHON}, found ${ACTUAL_PYTHON}." >&2
  exit 2
fi

for command in git docker ssh chia ray; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Missing required command: ${command}" >&2
    exit 2
  fi
done

export THIS_MACHINE="${THIS_MACHINE:-$(hostname -I | awk '{print $1}')}"
export CHIA_WORK_DIR="${CHIA_WORK_DIR:-${ROOT_DIR}}"
export USER="${USER:-$(id -un)}"

if [[ -z "${THIS_MACHINE}" ]]; then
  echo "Could not determine THIS_MACHINE. Export it to an SSH-reachable host IP." >&2
  exit 2
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not usable by the current user." >&2
  exit 2
fi

if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "${THIS_MACHINE}" true >/dev/null 2>&1; then
  cat >&2 <<EOF
SSH public-key authentication to ${THIS_MACHINE} failed.
CHIA requires the head machine to SSH to itself/worker hosts non-interactively.
Add/load the appropriate key, then retry.
EOF
  exit 2
fi

python scripts/gate_a2_preflight.py --output results/gate-a2-host-preflight.json

images=(
  ghcr.io/ucb-bar/chia-chisel-build:latest
  ghcr.io/ucb-bar/chia-verilator-run:latest
  ghcr.io/ucb-bar/chia-riscv-cross:latest
)

for image in "${images[@]}"; do
  echo "Checking image manifest: ${image}"
  docker manifest inspect "${image}" >/dev/null
done

python - <<'PY'
import shutil
from pathlib import Path

usage = shutil.disk_usage(Path.cwd())
print(f"free_disk_gib={usage.free / (1024**3):.1f}")
try:
    import os
    pages = os.sysconf('SC_PHYS_PAGES')
    page_size = os.sysconf('SC_PAGE_SIZE')
    print(f"physical_memory_gib={pages * page_size / (1024**3):.1f}")
except (ValueError, OSError, AttributeError):
    pass
PY

echo "Gate A.2 host preflight: PASS"
echo "THIS_MACHINE=${THIS_MACHINE}"
echo "Next command: bash scripts/run_gate_a2_build.sh"
