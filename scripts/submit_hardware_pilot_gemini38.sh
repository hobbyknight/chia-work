#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

MODEL="gemini-3.8-flash"
PROJECT="a3-chia-hack26ath-7706"
LOCATION="global"
OUT="/home/devstar7706/chia-work/results/hardware-pilot-gemini-3.8-flash.jsonl"
WARM="/home/devstar7706/chia-work/results/hardware-pilot-gemini-3.8-flash-warmup.jsonl"

mkdir -p /home/devstar7706/chia-work/results logs

for f in "$OUT" "$WARM"; do
  if [[ -e "$f" ]]; then
    echo "Refusing to overwrite existing evidence: $f" >&2
    exit 1
  fi
done

python - <<'PY'
from chia_work.gemini_agent import GeminiTypedActionAgent
agent = GeminiTypedActionAgent()
print(f"default_gemini_model={agent.model}")
if agent.model != "gemini-3.8-flash":
    raise SystemExit("default Gemini model is not gemini-3.8-flash")
PY

echo "=== SUBMIT HARDWARE PILOT WITH GEMINI 3.8 FLASH ==="

chia job submit \
  --runtime-env-json="$(cat <<JSON
{
  "env_vars": {
    "GOOGLE_GENAI_USE_ENTERPRISE": "true",
    "GOOGLE_CLOUD_PROJECT": "$PROJECT",
    "GOOGLE_CLOUD_LOCATION": "$LOCATION",
    "GEMINI_MODEL": "$MODEL"
  }
}
JSON
)" \
  --working-dir . \
  -- python scripts/run_real_hardware_pilot.py \
    --model "$MODEL" \
    --output "$OUT" \
    --warmup-output "$WARM"

echo "Submitted Gemini 3.8 Flash hardware pilot."
echo "output=$OUT"
echo "warmup_output=$WARM"
