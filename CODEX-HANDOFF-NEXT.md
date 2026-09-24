# Codex handoff — frozen state for Gemini-owned global loop

> **Historical status record.** This execution-time handoff is retained for provenance and is superseded for reviewer navigation by `README.md` and the packaged indexes in `docs/release/`. Do not follow its operational next steps during release reproduction.

## A. Project objective

Gemini 3.8 Flash is to become the sole agent and global orchestrator. Human, ChatGPT, and Codex are supervisors only.

## B. Architecture ownership

| Owner | Responsibility |
|---|---|
| Human | Mission/constraints, emergency intervention, quota and account authority. |
| ChatGPT | Audit and advice only. |
| Codex | Supervisor, watchdog, and control-plane only. |
| Gemini 3.8 Flash | Inner task reasoning, TypedAction proposals, SafetyGate feedback repair, verifier-failure diagnosis, and outer experiment/state-loop decisions after the current H1 batch. |
| SafetyGate | Policy enforcement. |
| CHIA / Ray | Orchestration and execution. |
| Chipyard / Gemmini / Verilator | Real HW/SW backend. |

## C. Completed milestones

- A.0 repository/control plane.
- A.1 real CHIA `@ChiaFunction`.
- A.2 host preflight.
- A.2 real Gemmini simulator.
- H0 sanity.
- H1 real upstream `mvin_mvout`.
- A.3 Gemini → SafetyGate → CHIA → Gemmini → Verilator.
- Gemini 3.8 Flash pilot attempt 3: complete U0/S1/S2/S3/S4 independent dataset.
- Attempt-3 evidence is frozen and Google Drive SHA256-verified.

## D. Historical failed and partial attempts

- Pilot attempt 1 (`raysubmit_2Zua24Fh1x9EYpWR`) is immutable partial evidence: 4/5 rows, then HTTP 429 before S4.
- Pilot attempt 2 (`raysubmit_b6mbiNRazgcRB7PR`) is immutable: warm-up only, then HTTP 429 before U0.
- Packaged H1 Ray submission (`raysubmit_fKxwKBSHt5UYsSNt`) is a separate control-plane failure. It failed before Gemini, warm-up, or hardware execution because the Ray working-directory package omitted untracked prior-gate evidence required by the frozen runner.

Never combine any of these with later datasets.

## E. Current active H1 main run

Snapshot time: `2026-09-22T02:51:16.332081+00:00`.

```text
PID=300023
state=RUNNING
user=devstar7706
command=python scripts/run_frozen_h1_suite.py --manifest configs/manifests/h1-main-v1.json --model gemini-3.8-flash
warmup_rows=1
comparative_rows=11
variant_counts=U0:2,S1:2,S2:3,S3:2,S4:2
log=logs/h1-main-v1-direct-20260922T021829Z.log
warmup_output=results/h1-main-v1-warmup.jsonl
comparative_output=results/h1-main-v1.jsonl
model=gemini-3.8-flash
GOOGLE_GENAI_USE_ENTERPRISE=true
GOOGLE_CLOUD_PROJECT=a3-chia-hack26ath-7706
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=gemini-3.8-flash
```

The process is also visible as Ray driver job `0c000000`. At the snapshot, the cluster had `verilator_run=1` in use and the three Docker workers were healthy. One bounded API retry was observed: `429 RESOURCE_EXHAUSTED`, delay 5 seconds; execution continued. Do not stop or restart this process while it is healthy.

The immutable VM/Drive snapshot is:

- `results/h1-main-v1-live-snapshot-20260922T025113Z.json`
- `results/h1-main-v1-live-snapshot-20260922T025113Z.jsonl`
- `results/h1-main-v1-live-snapshot-20260922T025113Z-warmup.jsonl`
- `logs/h1-main-v1-direct-20260922T021829Z-live-snapshot-20260922T025113Z.log`
- `results/h1-main-v1-live-snapshot-20260922T025113Z-SHA256SUMS.txt`

## F. Frozen experiment assets

- H1 main manifest: `configs/manifests/h1-main-v1.json`; entrypoint: `scripts/run_frozen_h1_suite.py`.
- Safety manifest: `configs/manifests/safety-v1.json`; entrypoint: `scripts/run_frozen_safety.py`.
- Recovery manifest: `configs/manifests/recovery-v1.json`; existing validation entrypoint: `scripts/validate_experiment_manifests.py`. A dedicated recovery execution entrypoint is not present in the current tree.

## G. Current scientific protocol

H1 uses valid `mvin_mvout` real hardware execution to measure utility preservation and overhead across five variants and five repetitions.

Safety measures unsafe/invalid-action prevention, records counterfactual unsafe U0 behavior, and never destructively executes unsafe actions.

Recovery must prove the Gemini feedback/repair loop, preserve complete attempt history, and distinguish pre-execution repair from post-verification repair.

## H. New architecture direction

After the current H1 main batch completes and is frozen, Codex must not autonomously sequence later experiments. Implement a Gemini-owned outer loop:

```text
Mission/current state
  → Gemini 3.8 Flash
  → typed outer action
  → state/policy validator
  → deterministic executor
  → observation/result
  → Gemini
  → repeat
```

Gemini owns deciding the next legal experiment stage, inspecting results, deciding retry or advance, identifying missing evidence, and declaring completion. Codex must not own those decisions.

## I. Outer-loop allowed action concept

The constrained outer action set is:

- `INSPECT_STATE`
- `RUN_FROZEN_STAGE`
- `MONITOR_STAGE`
- `FREEZE_EVIDENCE`
- `VERIFY_EVIDENCE`
- `BACKUP_EVIDENCE`
- `ANALYZE_RESULTS`
- `RETRY_STAGE`
- `ADVANCE_STAGE`
- `DECLARE_COMPLETE`

Gemini must not receive arbitrary raw-shell authority.

## J. Supervisor intervention conditions

Codex may intervene only for an unsafe/destructive request, evidence-integrity risk, source or manifest mutation, duplicate run, secret-exposure risk, runaway resources, broken authentication, unrecoverable infrastructure failure, or explicit human stop.

## K. Exact next action for the next session

`Monitor existing H1 PID only; do not submit another H1 run.`

After H1 is complete: freeze and validate H1, then implement and validate the Gemini-owned outer-loop harness before independently starting safety or recovery.

## Evidence inventory

VM root: `/home/devstar7706/chia-work`. Drive root: `/content/drive/MyDrive/CHIA-Hackathon/evidence/`.

Preserved evidence includes immutable pilot attempts 1 and 2, the successful Gemini health probe before attempt 3, complete pilot attempt 3, pre-main environment provenance, the packaged-H1 failure log, current direct-H1 snapshots, existing SHA256 manifests, and all terminal/checkpoint markers. Do not overwrite historical evidence.
