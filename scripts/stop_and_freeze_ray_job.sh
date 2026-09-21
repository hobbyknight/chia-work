#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <ray-job-id>" >&2
  exit 2
fi

JOB="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

mkdir -p logs results

parse_state() {
  tr '[:lower:]' '[:upper:]' \
    | grep -Eo 'PENDING|RUNNING|SUCCEEDED|FAILED|STOPPED' \
    | tail -n 1 || true
}

status_text="$(ray job status "$JOB" 2>&1 || true)"
printf '%s\n' "$status_text"
state="$(printf '%s\n' "$status_text" | parse_state)"

echo "detected_state=${state:-UNKNOWN}"

pre_log="logs/${JOB}-pre-stop.log"
ray job logs "$JOB" >"$pre_log" 2>&1 || true

case "$state" in
  PENDING|RUNNING)
    echo "Stopping Ray job $JOB"
    ray job stop "$JOB"
    ;;
  SUCCEEDED|FAILED|STOPPED)
    echo "Ray job $JOB is already terminal; no stop request needed"
    ;;
  *)
    echo "Could not determine Ray job state; refusing to guess" >&2
    exit 1
    ;;
esac

for _ in $(seq 1 30); do
  status_text="$(ray job status "$JOB" 2>&1 || true)"
  state="$(printf '%s\n' "$status_text" | parse_state)"
  case "$state" in
    SUCCEEDED|FAILED|STOPPED) break ;;
  esac
  sleep 2
done

printf '%s\n' "$status_text"
echo "final_state=${state:-UNKNOWN}"

final_log="logs/${JOB}.log"
ray job logs "$JOB" >"$final_log" 2>&1 || true

for src in \
  results/hardware-pilot-warmup.jsonl \
  results/hardware-pilot.jsonl
  do
  if [[ -f "$src" ]]; then
    base="$(basename "$src" .jsonl)"
    dst="results/${base}-${JOB}-partial.jsonl"
    cp -p "$src" "$dst"
    echo "frozen_partial=$dst"
  fi
done

manifest="results/${JOB}-partial-SHA256SUMS.txt"
: >"$manifest"
for f in \
  "$pre_log" \
  "$final_log" \
  results/*-"$JOB"-partial.jsonl
  do
  if [[ -f "$f" ]]; then
    sha256sum "$f" >>"$manifest"
  fi
done

cat "$manifest"
echo "Stopped/frozen job: $JOB"
