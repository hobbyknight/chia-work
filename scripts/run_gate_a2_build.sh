#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# shellcheck disable=SC1091
source .venv/bin/activate

export THIS_MACHINE="${THIS_MACHINE:-$(hostname -I | awk '{print $1}')}"
export CHIA_WORK_DIR="${CHIA_WORK_DIR:-${ROOT_DIR}}"
export USER="${USER:-$(id -un)}"

CLUSTER_CONFIG="${CLUSTER_CONFIG:-configs/chia-gemmini-local.yaml}"
RESULT_PATH="${RESULT_PATH:-${ROOT_DIR}/results/real-gemmini-build.jsonl}"
JOB_LOG="${JOB_LOG:-${ROOT_DIR}/logs/gate-a2-gemmini-build.log}"
MAKE_JOBS="${MAKE_JOBS:-16}"
BUILD_TIMEOUT_SECONDS="${BUILD_TIMEOUT_SECONDS:-3600}"

mkdir -p "$(dirname "${RESULT_PATH}")" "$(dirname "${JOB_LOG}")"

./scripts/preflight_gate_a2_host.sh

echo "Bringing up CHIA cluster: ${CLUSTER_CONFIG}"
chia up "${CLUSTER_CONFIG}"

cleanup() {
  status=$?
  echo "Tearing down CHIA cluster..."
  chia down "${CLUSTER_CONFIG}" || true
  exit "${status}"
}
trap cleanup EXIT INT TERM

echo "Submitting real GemminiRocketConfig build through CHIA..."
set -o pipefail
chia job submit --working-dir . -- \
  python scripts/real_gemmini_build.py \
    --output "${RESULT_PATH}" \
    --jobs "${MAKE_JOBS}" \
    --timeout-seconds "${BUILD_TIMEOUT_SECONDS}" \
  2>&1 | tee "${JOB_LOG}"

python - <<PY
import json
from pathlib import Path

path = Path(${RESULT_PATH@Q})
if not path.exists():
    raise SystemExit(f"Gate A.2 result file was not created: {path}")
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
if not rows:
    raise SystemExit("Gate A.2 result file is empty")
record = rows[-1]
assert record["mocked"] is False, record
assert record["verification"] == "PASS", record
assert record["safety_decision"] == "ALLOW", record
tool = record["tool_result"]
assert tool["backend"] == "chia-chipyard-chisel-build", tool
assert tool["config"] == "GemminiRocketConfig", tool
assert tool["simulator_binary_size_bytes"] > 0, tool
assert tool["simulator_binary_sha256"], tool
print("Gate A.2 real Gemmini build evidence: PASS")
print(f"simulator={tool['simulator_binary_name']}")
print(f"size_bytes={tool['simulator_binary_size_bytes']}")
print(f"sha256={tool['simulator_binary_sha256']}")
PY

echo "Gate A.2 PASS"
echo "Evidence: ${RESULT_PATH}"
echo "Job log: ${JOB_LOG}"
