# CURRENT PLAN

Updated: 2026-09-18 (Asia/Bangkok / Vietnam time)

## Objective

Deliver a competitive CHIA Hackathon submission around a SafeAgent layer for agentic HW/SW co-design, with a reproducible CHIA loop, real Gemmini results, a 4-page paper, and a public artifact release.

## Current state in one sentence

**Architecture/harness work for Gate A is wired; the only critical Sep 18 gap is real execution evidence.**

## Critical path

### Sep 18 — Make it run

- [x] Initialize dedicated repository.
- [x] Create control-plane, architecture, experiment, GCP, paper, and submission scaffolding.
- [x] Implement typed-action + SafetyGate + JSONL logging harness.
- [x] Pin official CHIA source revision and Python 3.10.19 bootstrap procedure.
- [x] Implement a real `@ChiaFunction`/Ray smoke path.
- [x] Implement real `ChiselBuildNode` → `GemminiRocketConfig` build path.
- [x] Implement schema-constrained Gemini → TypedAction proposal path.
- [x] Implement real CHIA build → RISC-V build → Verilator H0 sanity path.
- [x] Implement real H1 Gemmini `mvin_mvout` accelerator workload.
- [x] Implement exact U0/S1/S2/S3/S4 semantics and S4 feedback retry loop.
- [x] Implement non-executing safety challenge suite.
- [x] Implement cached/incremental U0–S4 hardware pilot runner.
- [ ] **Execute `make real-chia` and capture first successful `mocked=false` record.**
- [ ] **Execute H1 `mvin_mvout` once and capture a successful real accelerator record.**
- [ ] **Execute Gemini → SafetyGate → H1 and capture the first full agentic hardware record.**

Gate A is NOT considered passed merely because all paths are implemented.

### Sep 19 — Make it measurable

Implementation prep is already ahead of this day's original plan:

- [x] Define exact U0/S1/S2/S3/S4 functionality in code.
- [x] Define initial safety challenge suite.
- [x] Define H1 primary hardware workload.
- [x] Define environment/source/binary provenance capture.
- [ ] Run `make safety-challenges` and inspect labels/results.
- [ ] Run first real `make hardware-pilot`.
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
