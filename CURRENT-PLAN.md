# CURRENT PLAN

Updated: 2026-09-18 (Asia/Bangkok / Vietnam time)

## Objective

Deliver a competitive CHIA Hackathon submission around a SafeAgent layer for agentic HW/SW co-design, with a reproducible CHIA loop, real results, a 4-page paper, and a public artifact release.

## Critical path

### Sep 18 — Make it run

- [x] Initialize dedicated repository.
- [x] Create control-plane, architecture, experiment, GCP, paper, and submission scaffolding.
- [x] Implement local typed-action + SafetyGate + JSONL logging dry-run harness.
- [ ] Bootstrap official CHIA using Python 3.10.19.
- [ ] Identify the exact real tool path for the first target workload.
- [ ] Execute one real CHIA tool call.
- [ ] Connect one real Gemmini/Chipyard build or simulation operation.
- [ ] Demonstrate one end-to-end real path: agent/driver → SafetyGate → tool → verification → log.

### Sep 19 — Make it measurable

- [ ] Freeze U0/S1/S2/S3/S4 definitions.
- [ ] Freeze benchmark tasks and fault-injection cases.
- [ ] Freeze primary metrics and main result table schema.
- [ ] Run small local pilot across all variants.
- [ ] Fix logging and result collection before scale-up.

### Sep 20 — Make it reproducible

- [ ] Rehearse fresh-clone bootstrap.
- [ ] Rehearse GCP project/key swap using environment variables only.
- [ ] Freeze code used for funded runs.
- [ ] Prepare run manifests for all compute-day jobs.
- [ ] Draft paper sections 1–6 and pre-create result figures/tables.
- [ ] Ensure HotCRP title/authors/basic abstract are registered.

### Sep 21 — Compute day 1

- [ ] Receive/migrate to funded GCP account.
- [ ] Smoke test on funded infrastructure.
- [ ] Run U0 baseline first.
- [ ] Run S1/S2 and preserve raw logs.

### Sep 22 — Compute day 2

- [ ] Run S3/S4.
- [ ] Run repetitions for primary metrics.
- [ ] Generate interim main table and identify missing cells.

### Sep 23 — Compute day 3

- [ ] Fill missing cells.
- [ ] Run only high-value ablations/reruns.
- [ ] Freeze all compute-backed results before account shutdown.

### Sep 24 — Package and submit

- [ ] Convert raw logs → final tables/figures.
- [ ] Finish 4-page double-column ACM/IEEE-style PDF.
- [ ] Add AI-assistance acknowledgment.
- [ ] Publish/release repository + results publicly.
- [ ] Verify clean-room reproduction instructions.
- [ ] Submit PDF and artifact URL to HotCRP before Sep 24 AoE.

## Scope lock

Until Gate A passes, do not add unrelated agents, frontends, dashboards, or additional hardware targets. First target one small, measurable CHIA/Gemmini path.
