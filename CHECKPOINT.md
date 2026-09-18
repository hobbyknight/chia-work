# CHECKPOINT

Snapshot: 2026-09-18 Gate A implementation wired; execution evidence pending.

## What is confirmed

- Dedicated repo exists and is writable.
- Short-term funded account has been confirmed by hackathon organizers for Sep 21–23.
- Official final deadline is Sep 24 AoE.
- Official final submission requires a 4-page paper and an open-sourced loop/results artifact.
- Typed actions, SafetyGate, structured JSONL logging, result schema, experiment matrix and dry-run harness are in-tree.
- Upstream CHIA is pinned to commit `16c35e92aaaf9511c6453bf94cd5cf589698f4e3` for reproducibility.
- Gate A.1 implementation exists: `ChiaLocalExecutor` dispatches a real `@ChiaFunction` and verifies the typed-action SHA on return.
- Gate A.2 implementation exists: `GemminiChiselBuildExecutor` calls upstream `ChiselBuildNode.build` for `GemminiRocketConfig`.
- Single-host CHIA cluster template contains both `chipyard` and `verilator_run` workers.
- Real-executor failures are preserved as structured non-mocked failed records instead of being lost to an exception.

## What is NOT yet proven

- We have not yet captured a successful `mocked=false` CHIA smoke record from an execution environment with CHIA installed.
- We have not yet captured a successful `GemminiRocketConfig` Verilator build artifact.
- No real Gemini API call has been executed from this repository yet.
- No complete Gemini → SafetyGate → CHIA → Gemmini → verification feedback loop has been demonstrated yet.
- No paper result is available yet.

## Current gate

**Gate A: capture execution evidence for the wired real paths.**

Pass condition:

```text
real task/driver
  → typed action
  → SafetyGate decision
  → CHIA-backed real execution
  → verification
  → structured record with mocked=false
```

Gate A is split into:

- **A.1 runtime proof:** `make real-chia` must PASS and write `results/real-chia-smoke.jsonl`.
- **A.2 hardware proof:** `make gemmini-up && make real-gemmini` must build a non-empty Gemmini Verilator simulator and write `results/real-gemmini-build.jsonl`.

## Exact execution order

```bash
make test
bash scripts/bootstrap_chia.sh
make real-chia

export THIS_MACHINE=$(hostname -I | awk '{print $1}')
export CHIA_WORK_DIR=$(pwd)
export USER=$(id -un)
make gemmini-up
make real-gemmini
make gemmini-down
```

## Environment note

An external validation attempt from the assistant runtime could not download Python 3.10.19 because that runtime has no outbound DNS. This does not count as a project failure and does not satisfy Gate A either; execution evidence must come from GitHub Actions or the development/GCP environment.

## Immediate next actions after A.1/A.2 pass

1. Connect Gemini structured output to `TypedAction`.
2. Add at least one real Gemmini benchmark run after the simulator build.
3. Implement post-execution oracle and retry/recovery path.
4. Run the first U0/S1/S2/S3/S4 pilot set before the Sep 19 experiment freeze.
