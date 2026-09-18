# CHECKPOINT

Snapshot: 2026-09-18 Gate A implementation is wired through a real Gemmini simulator run; execution evidence is pending.

## What is confirmed in-tree

- Dedicated repo exists and is writable.
- Short-term funded account has been confirmed for Sep 21–23; final deadline is Sep 24 AoE.
- Typed actions, SafetyGate, structured JSONL logging, result schema, experiment matrix and dry-run harness exist.
- Upstream CHIA is pinned to commit `16c35e92aaaf9511c6453bf94cd5cf589698f4e3`.
- Gate A.1: `ChiaLocalExecutor` dispatches a real `@ChiaFunction` and verifies action SHA on return.
- Gate A.2: `GemminiChiselBuildExecutor` calls upstream `ChiselBuildNode.build` for `GemminiRocketConfig`.
- Gate A.3: `GeminiTypedActionAgent` uses schema-constrained Gemini output and can drive the real CHIA smoke.
- Gate A.4: Gemini can propose the semantically constrained real Gemmini build action.
- Gate A.5: `GemminiSanityRunExecutor` composes official CHIA `ChiselBuildNode`, `RiscvBuildNode`, and `VerilatorRunNode` to build the Gemmini SoC, compile a bare-metal ELF, execute it, and verify the marker `SAFEAGENT_GEMMINI_SANITY_PASS`.
- Gate A.6: a full Gemini → TypedAction → SafetyGate → CHIA → Gemmini build/compile/run script exists.
- Cluster config exposes `chipyard`, `riscv_build`, and `verilator_run` workers using official CHIA images.
- SafetyGate has semantic policies for `chia-local-smoke`, `gemmini-verilator`, and `gemmini-sanity-run`, including action/config/resource-budget constraints.
- Executor failures are preserved as structured non-mocked failed records instead of disappearing as exceptions.

## What is NOT yet proven by execution evidence

- No successful `mocked=false` CHIA smoke record has yet been captured.
- No successful `GemminiRocketConfig` Verilator build record has yet been captured.
- No successful Gemmini simulator run record with the sanity marker has yet been captured.
- No real Gemini API/GCP call has yet been captured from this repository.
- Therefore no paper result is considered valid yet.

## Gate A pass condition

```text
Gemini/task driver
  → schema-constrained TypedAction
  → SafetyGate
  → CHIA scheduling
  → Chipyard Gemmini build
  → RISC-V ELF build
  → Verilator execution
  → post-execution marker verification
  → structured record with mocked=false
```

The strongest Gate A evidence is A.6. A.1 and A.5 are useful isolation checkpoints when debugging.

## Exact execution order

```bash
make test
bash scripts/bootstrap_chia.sh
make real-chia

# Configure Gemini credentials: funded GCP ADC is preferred.
cp .env.example .env
# Export the populated values in .env using your shell/environment tooling.
make real-agent

export THIS_MACHINE=$(hostname -I | awk '{print $1}')
export CHIA_WORK_DIR=$(pwd)
export USER=$(id -un)
make gemmini-up

# Isolated hardware checks
make real-gemmini
make real-gemmini-sanity

# Full agentic hardware path
make real-agent-gemmini-sanity

make gemmini-down
```

## Expected evidence files

```text
results/real-chia-smoke.jsonl
results/real-gemini-chia-smoke.jsonl
results/real-gemmini-build.jsonl
results/real-gemmini-sanity.jsonl
results/real-gemini-gemmini-sanity.jsonl
```

Every record intended as real evidence must contain `mocked=false`; successful runs must also have `verification=PASS`.

## Environment note

An external validation attempt from the assistant runtime could not download Python 3.10.19 because that runtime has no outbound DNS. This does not count as a project failure and does not satisfy Gate A. GitHub Actions or the development/GCP environment must generate the execution evidence.

## Immediately after Gate A passes

1. Freeze task/fault families for U0/S1/S2/S3/S4.
2. Add deliberately invalid/unsafe proposals to quantify prevention and false rejection.
3. Add retry/repair feedback from SafetyGate and post-execution failures back to Gemini.
4. Replace the sanity ELF with actual Gemmini accelerator workloads for main results.
5. Run a small pilot before the Sep 19 experiment freeze.
