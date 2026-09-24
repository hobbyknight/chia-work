# Codex handoff — control-plane only

> **Historical status record.** This execution-time handoff is retained for provenance and is superseded for reviewer navigation by `README.md` and the packaged indexes in `docs/release/`. Do not follow its operational next steps during release reproduction.

## Role boundary

Codex is only the control-plane operator for this repository. It must not invent hardware/software actions, rewrite experiment prompts, alter SafetyGate policy, modify workloads, rebuild Chipyard/Gemmini, or substitute its own reasoning for the experiment agent.

All experiment action proposals must be produced by `GeminiTypedActionAgent` using `gemini-3.8-flash`. Deterministic setup/warm-up, SafetyGate evaluation, CHIA/Ray dispatch, Gemmini/Verilator execution, post-hoc verification, logging, hashing, and backup are infrastructure/control-plane operations and are not agent proposals.

## Frozen state before handoff

Already PASS; do not rerun just for confidence:

- A.0 repo/control plane
- A.1 real CHIA `@ChiaFunction`
- A.2 host preflight
- A.2 real Gemmini simulator build
- H0 sanity
- H1 `mvin_mvout`
- A.3 Gemini -> SafetyGate -> CHIA -> Gemmini -> Verilator

Existing Ray workers/resources and Docker containers are healthy. Do not restart Ray or Docker unless a concrete failure proves that is required.

Previous pilot job:

`raysubmit_9strJ581H9sPKSLx`

That pilot was submitted before the default model migration and may contain `gemini-2.5-flash` proposals. It must not be mixed with the final Gemini 3.8 experiment data.

## Required execution order

1. On the GCP VM repo, inspect `git status --short`. Do not discard local changes.
2. Fast-forward the repo to current `origin/main`. If a fast-forward is blocked by local changes, stop and report the exact files; do not reset or overwrite them.
3. Stop/freeze only the previous pilot by invoking:

   `bash scripts/stop_and_freeze_ray_job.sh raysubmit_9strJ581H9sPKSLx`

4. Confirm the old Ray job is terminal (`STOPPED`, `FAILED`, or `SUCCEEDED`). Never submit a replacement while it is still `RUNNING` or `PENDING`.
5. Submit the replacement pilot only by invoking:

   `bash scripts/submit_hardware_pilot_gemini38.sh`

6. Record the new Ray job ID. Monitor that exact job only. Do not submit duplicates.
7. When terminal, save its Ray log to the persistent repo, inspect the warm-up and 5 comparative records, calculate SHA256, and back up the evidence to the established Google Drive evidence directory.
8. Do not start the frozen 5x5 H1 main experiment until the Gemini 3.8 pilot has terminal evidence and the pilot results have been inspected.

## Hard prohibitions

- No A.2/H0/H1 rebuild or rerun without a concrete failure reason.
- No new VM.
- No Ray/Docker restart while the cluster is healthy.
- No `git reset --hard`, forced checkout, or deletion of evidence.
- No manual editing of JSONL evidence.
- No substitution of Codex-generated TypedAction for Gemini-generated actions.
- No final PASS claim from `job submitted successfully`; PASS requires result artifacts.
- No mixing partial Gemini 2.5 pilot rows with Gemini 3.8 final pilot/main rows.

## Gemini model invariant

The repository default is `gemini-3.8-flash`. The submit wrapper also pins both `GEMINI_MODEL=gemini-3.8-flash` in Ray runtime env and `--model gemini-3.8-flash` on the pilot command line. A result row whose `agent.model` is not `gemini-3.8-flash` is not eligible for the Gemini 3.8 experiment dataset.
