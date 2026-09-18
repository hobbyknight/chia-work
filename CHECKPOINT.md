# CHECKPOINT

Snapshot: 2026-09-18 — Gate A code path is complete through a real Gemmini accelerator workload; execution evidence is pending.

## Confirmed in-tree

- Upstream CHIA is pinned to commit `16c35e92aaaf9511c6453bf94cd5cf589698f4e3`; bootstrap requires Python 3.10.19.
- `ChiaLocalExecutor` provides a real `@ChiaFunction`/Ray round-trip proof.
- `GeminiTypedActionAgent` uses a constrained structured-output schema; arbitrary parameter keys are not accepted.
- `ChiselBuildNode` builds `GemminiRocketConfig` through CHIA.
- H0 composes `ChiselBuildNode` + `RiscvBuildNode` + `VerilatorRunNode` and checks a marker.
- H1 uses upstream Gemmini `mvin_mvout-baremetal`, which exercises Gemmini memory movement and self-checks matrix equality.
- U0/S1/S2/S3/S4 semantics are explicit in `src/chia_work/variants.py`.
- S4 feedback/retry is implemented in `src/chia_work/agentic_loop.py` with complete attempt history.
- Counterfactual safety challenges never execute unsafe U0 actions.
- Real hardware pilot performs a setup warm-up excluded from comparative timing, then U0–S4 on the same incremental/cached environment.
- Environment capture records source revisions, Python/package versions and Docker IDs/digests.
- Cluster config exposes `chipyard`, `riscv_build`, and `verilator_run` workers.

## NOT yet proven by execution evidence

- `make real-chia` has not yet produced a successful local `mocked=false` artifact observed by us.
- H1 `mvin_mvout` has not yet produced a successful real Verilator result observed by us.
- Gemini → SafetyGate → H1 has not yet produced a successful full agentic accelerator artifact observed by us.
- Therefore **Gate A is OPEN and paper result cells remain empty**.

## Gate A pass condition

Strongest required evidence:

```text
Gemini
  → schema-constrained TypedAction
  → SafetyGate
  → CHIA
  → GemminiRocketConfig simulator
  → upstream mvin_mvout-baremetal
  → VerilatorRunNode
  → upstream self-checking exit code 0
  → structured JSONL with mocked=false
```

Isolation checkpoints should be run first so failures can be localized.

## Exact execution order

```bash
# No external runtime needed
make test
make safety-challenges

# Real CHIA
bash scripts/bootstrap_chia.sh
make real-chia

# Real Gemini; funded GCP/ADC preferred
# Export values described in .env.example
make real-agent

# Real hardware cluster
export THIS_MACHINE=$(hostname -I | awk '{print $1}')
export CHIA_WORK_DIR=$(pwd)
export USER=$(id -un)
make gemmini-up
make capture-env

# Isolation
make real-gemmini
make real-gemmini-sanity

# Primary accelerator evidence
make real-gemmini-mvin-mvout
make real-agent-gemmini-mvin-mvout

# Pilot once H1 passes
make hardware-pilot

make gemmini-down
```

## Expected evidence files

```text
results/environment.json
results/safety-challenges.jsonl
results/safety-challenges-summary.json
results/real-chia-smoke.jsonl
results/real-gemini-chia-smoke.jsonl
results/real-gemmini-build.jsonl
results/real-gemmini-sanity.jsonl
results/real-gemmini-mvin-mvout.jsonl
results/real-gemini-gemmini-mvin-mvout.jsonl
results/hardware-pilot-warmup.jsonl
results/hardware-pilot.jsonl
```

Real hardware/agent evidence must contain `mocked=false`. Unsafe safety-challenge cases are different: they are explicitly `counterfactual_only=true`, `executed=false`.

## Environment limitation observed during this work

The assistant's separate execution container could not download Python/CHIA because outbound DNS was unavailable. This is not project evidence and not a project failure. A development machine, suitable GitHub runner, or GCP environment with Docker/Ray must create the real artifacts.

## Next after first H1 pass

1. Inspect pilot logs for integration mistakes only.
2. Freeze safety labels, recovery cases, repetitions and variant ordering on Sep 19.
3. Do not add another accelerator workload until the U0–S4 main table is complete.
4. Start writing paper architecture/method sections immediately; results remain TBD until real runs.
