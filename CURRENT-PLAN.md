# CURRENT PLAN

Updated: 2026-09-21 (UTC)

## Objective

Deliver a competitive CHIA Hackathon submission around a SafeAgent layer for agentic HW/SW co-design, with a reproducible CHIA loop, real Gemmini results, a 4-page paper, and a public artifact release.

## Current state in one sentence

**The real CHIA/Gemmini/Verilator path is proven. Gemini 3.8 pilot attempts 1 and 2 are frozen after HTTP 429 `RESOURCE_EXHAUSTED`; a fresh Gemini-only health probe passed on 2026-09-22, so the capacity blocker is resolved operationally and one isolated attempt 3 may be submitted.**

## Active execution lock

- [x] Freeze pilot attempt 1 raw evidence and full Ray log on the GCP VM.
- [x] Back up attempt 1 to Google Drive and verify matching SHA256 hashes.
- [x] Preserve attempt 1 as an immutable 4-row partial dataset.
- [x] Run a Gemini-only structured TypedAction health probe with `gemini-3.8-flash` using the funded project authentication path; freeze it on VM/Drive with matching hashes.
- [x] Add and test bounded retry handling for transient Gemini API 429/503 responses without changing experiment semantics.
- [x] Run a complete isolated pilot attempt 2 with new output names; it stopped before U0 after the warm-up because all bounded Gemini API retries returned 429.
- [x] Re-run the Gemini-only structured TypedAction health probe after attempt 2 and freeze matching VM/Drive evidence.
- [ ] Submit, freeze, and validate one complete isolated five-row pilot attempt 3 before H1 main.

Attempt 1 and attempt 2 are immutable and must not be merged with any future attempt. The historical capacity blocker is documented in their checkpoints. The fresh probe recorded in `docs/experiments/pilot-38-attempt-3-health-probe-checkpoint.md` permits one new, completely independent pilot attempt; H1 main remains locked until a single five-row pilot is frozen.

## Critical path

### Sep 18 — Make it run

- [x] Initialize dedicated repository.
- [x] Create control-plane, architecture, experiment, GCP, paper, and submission scaffolding.
- [x] Implement typed-action + SafetyGate + JSONL logging harness.
- [x] Pin official CHIA source revision and Python 3.10.19 bootstrap procedure.
- [x] Execute real `@ChiaFunction`/Ray smoke path and capture `mocked=false` evidence (Gate A.1).
- [x] Implement real `ChiselBuildNode` → `GemminiRocketConfig` build path.
- [x] Validate Gate A.2 cluster/SafetyGate/upstream API contract in GitHub Actions.
- [x] Add host preflight and one-command real Gate A.2 runner.
- [x] Implement schema-constrained Gemini → TypedAction proposal path.
- [x] Implement real CHIA build → RISC-V build → Verilator H0 sanity path.
- [x] Implement real H1 Gemmini `mvin_mvout` accelerator workload.
- [x] Implement exact U0/S1/S2/S3/S4 semantics and S4 feedback retry loop.
- [x] Implement non-executing safety challenge suite.
- [x] Implement cached/incremental U0–S4 hardware pilot runner.
- [ ] **On a suitable host, run `bash scripts/preflight_gate_a2_host.sh`.**
- [ ] **Run `bash scripts/run_gate_a2_build.sh` and capture a successful real Gemmini simulator artifact (Gate A.2).**
- [ ] Execute H1 `mvin_mvout` once and capture a successful real accelerator record.
- [ ] Execute Gemini → SafetyGate → H1 and capture the first full agentic hardware record.

Gate A is NOT considered passed merely because all paths are implemented or because the A.2 preflight passes.

### Sep 19 — Make it measurable

Implementation prep is already ahead of this day's original plan:

- [x] Define exact U0/S1/S2/S3/S4 functionality in code.
- [x] Define initial safety challenge suite.
- [x] Define H1 primary hardware workload.
- [x] Define environment/source/binary provenance capture.
- [ ] Run `make safety-challenges` and inspect labels/results.
- [ ] Run first real `make hardware-pilot` after Gate A.2/H1 pass.
- [ ] Freeze safety challenge case labels after inspection for mistakes only, before main-scale data.
- [ ] Freeze recovery task family.
- [ ] Freeze repetition count and variant scheduling/order.
- [ ] Freeze primary metrics and main result table schema.
- [ ] Fix any run/logging failure found by the pilot; do not expand scope.

### Sep 20 — Make it reproducible

- [ ] Rehearse fresh-clone bootstrap on a clean machine/VM.
- [ ] Run `make capture-env` after pulling all worker images; preserve image digests.
- [ ] Rehearse GCP project/key swap using environment variables only.
- [ ] Freeze code/revisions used for funded runs.
- [ ] Prepare run manifests for all compute-day jobs.
- [ ] Draft paper sections 1–6 and pre-create result figures/tables.
- [ ] Ensure HotCRP title/authors/basic abstract are registered.

### Sep 21 — Compute day 1

- [ ] Receive/migrate to funded GCP account.
- [ ] Smoke test on funded infrastructure.
- [ ] Capture funded environment provenance.
- [ ] Run U0 baseline and S1/S2 primary workload batches first.
- [ ] Preserve raw logs, prompts, usage metadata and hashes.

### Sep 22 — Compute day 2

- [ ] Run S3/S4 primary workload batches.
- [ ] Run frozen safety/recovery cases.
- [ ] Run repetitions for primary metrics.
- [ ] Generate interim main table and identify missing cells.

### Sep 23 — Compute day 3

- [ ] Fill missing main-table cells.
- [ ] Run only high-value ablations/reruns.
- [ ] Copy all raw evidence out of the funded account.
- [ ] Freeze compute-backed results before account shutdown.

### Sep 24 — Package and submit

- [ ] Convert real raw logs → final tables/figures.
- [ ] Finish 4-page double-column ACM/IEEE-style PDF.
- [ ] Add limitations and AI-assistance acknowledgment.
- [ ] Publish/release repository + results publicly.
- [ ] Verify no secrets and verify artifact URL while logged out.
- [ ] Verify clean-room reproduction instructions.
- [ ] Submit PDF and artifact URL to HotCRP before Sep 24 AoE.

## Scope lock

Until real H1 execution passes, do **not** add another accelerator, frontend, dashboard, model provider, or hardware target. `mvin_mvout` is the primary bring-up accelerator workload; additional Gemmini workloads are allowed only after the main U0–S4 table has no missing cells.
