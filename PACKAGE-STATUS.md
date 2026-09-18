# PACKAGE STATUS

Snapshot: 2026-09-18 after Gate A implementation pass.

Legend:

- `READY` = implementation/document is usable now.
- `WIRED-NOT-PROVEN` = real integration code exists but no successful execution artifact has yet been captured.
- `BLOCKED-EXTERNAL` = requires credentials/compute/environment not available to this repo operation.

| Area | Status | Notes |
|---|---|---|
| Control-plane docs | READY | README, current plan, checkpoint and package status synchronized |
| Official requirements snapshot | READY | Submission requirements recorded |
| Typed actions | READY | Explicit action enum/dataclass and schema-constrained Gemini output |
| SafetyGate generic checks | READY | S1 implementation |
| SafetyGate semantic policies | READY | S2+ target/config/path/resource-budget checks |
| Post-execution verification plumbing | READY | S3 ablation explicit in runner |
| Feedback repair/retry | READY | S4 loop with capped retries + attempt history |
| Structured logging | READY | JSONL, mocked flag, verification and retry fields |
| U0–S4 semantics | READY | Source of truth: `src/chia_work/variants.py` |
| Safety challenge suite | READY | Counterfactual only; never executes unsafe proposals |
| Environment provenance | READY | Source/package/Docker digest capture script |
| CHIA bootstrap | READY | Python 3.10.19 + upstream CHIA commit pinned |
| Real CHIA local executor | WIRED-NOT-PROVEN | Real `@ChiaFunction`/Ray SHA round trip implemented |
| Gemini typed-action agent | WIRED-NOT-PROVEN | Current Google Gen AI structured-output path implemented; credentials required to prove |
| Gemmini simulator build | WIRED-NOT-PROVEN | Official `ChiselBuildNode` + `GemminiRocketConfig` path implemented |
| H0 Gemmini sanity pipeline | WIRED-NOT-PROVEN | Chisel build + RISC-V build + Verilator marker oracle |
| H1 Gemmini `mvin_mvout` workload | WIRED-NOT-PROVEN | Uses upstream self-checking accelerator workload; exit 0 is pass oracle |
| Real U0–S4 hardware pilot | WIRED-NOT-PROVEN | Warm-up excluded, cached/incremental comparative run implemented |
| Unit/integration-logic tests | READY | Safety, runner, imports and S4 repair behavior covered; CI execution result still must be observed |
| GCP migration | READY | Env-only credential strategy + runbook |
| Funded GCP credentials | BLOCKED-EXTERNAL | Organizers send account details Sep 20 PDT |
| Real execution evidence | BLOCKED-EXTERNAL | Needs a machine/GitHub runner/GCP environment capable of installing CHIA and running Docker/Ray |
| Paper | SCAFFOLD | Architecture/method are writable now; result cells remain empty until real evidence |
| HotCRP submission | SCAFFOLD | Checklist prepared; registration/submission is a browser-side action |
| Public final release | BLOCKED-EXTERNAL | Working repo is private; make release/public artifact before final submission |

## Current truth

The project is no longer blocked on architecture or harness design. It is blocked on **executing the wired real paths and collecting evidence**. No paper result may be populated from dry-run, mocked, or merely implemented paths.
