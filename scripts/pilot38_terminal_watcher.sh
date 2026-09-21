#!/usr/bin/env bash
set -u

JOB="raysubmit_2Zua24Fh1x9EYpWR"
REPO="/home/devstar7706/chia-work"
FULL_LOG="$REPO/logs/${JOB}.log"
MANIFEST="$REPO/results/${JOB}-pilot38-SHA256SUMS.txt"
MARKER="$REPO/PILOT_38_TERMINAL_ON_VM"

cd "$REPO" || exit 1
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
mkdir -p logs results

while true; do
  status_text="$(ray job status "$JOB" 2>&1 || true)"
  printf '%s\n' "$status_text"
  state="$(printf '%s\n' "$status_text" | grep -Eo 'PENDING|RUNNING|SUCCEEDED|FAILED|STOPPED' | tail -n 1 || true)"
  if [[ -z "$state" ]]; then
    normalized="$(printf '%s\n' "$status_text" | tr '[:upper:]' '[:lower:]')"
    case "$normalized" in
      *" was stopped"*) state="STOPPED" ;;
      *" failed"*) state="FAILED" ;;
      *" finished successfully"*|*" succeeded"*) state="SUCCEEDED" ;;
    esac
  fi

  case "$state" in
    SUCCEEDED|FAILED|STOPPED)
      ray job logs "$JOB" >"$FULL_LOG" 2>&1 || true
      : >"$MANIFEST"
      for evidence in \
        results/hardware-pilot-gemini-3.8-flash-warmup.jsonl \
        results/hardware-pilot-gemini-3.8-flash.jsonl \
        "$FULL_LOG"
      do
        if [[ -f "$evidence" ]]; then
          sha256sum "$evidence" >>"$MANIFEST"
        fi
      done
      {
        echo "job_id=$JOB"
        echo "terminal_state=$state"
        echo "frozen_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "sha256_manifest=$MANIFEST"
      } >"$MARKER"
      echo "terminal_state=$state"
      echo "marker=$MARKER"
      exit 0
      ;;
  esac

  sleep 30
done
