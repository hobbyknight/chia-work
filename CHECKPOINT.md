# CHECKPOINT

Snapshot: 2026-09-22 — real CHIA/Gemmini/Verilator execution is proven. Gemini 3.8 pilot attempt 3 is a complete, frozen, independent U0–S4 dataset; frozen H1 main experiments may begin.

## Current operational checkpoint

```text
PILOT_38_ATTEMPT_3=PASS
ray_job_id=raysubmit_5mdm3zeyefHLH1cm
comparative_rows=5/5
variants=U0,S1,S2,S3,S4
agent_model=gemini-3.8-flash
mocked=false
gemmini_config=GemminiRocketConfig
pilot_lock=RELEASED
next_action=freeze_main_environment_and_submit_frozen_H1_main
```

The new health-probe record, full log, and SHA256 manifest are frozen on the VM and Google Drive with matching hashes; see `docs/experiments/pilot-38-attempt-3-health-probe-checkpoint.md`. This resolved the capacity gate operationally. It does not alter either historical pilot attempt.

Pilot attempt 3 then completed U0/S1/S2/S3/S4 in one independent execution. Every comparative row used `gemini-3.8-flash`, `mocked=false`, `GemminiRocketConfig`, exit code 0, and post-hoc task success. Its evidence is frozen and hash-verified on the VM and Drive; see `docs/experiments/pilot-38-attempt-3-checkpoint.md`.

Attempt 2 used independent filenames and bounded API-only retries. Its warm-up passed, then U0 proposal generation exhausted three retries after repeated HTTP 429 responses. No comparative or H1 job ran. Evidence is frozen on the VM and Drive with matching hashes; see `docs/experiments/pilot-38-attempt-2-checkpoint.md`.

Ray job `raysubmit_2Zua24Fh1x9EYpWR` completed U0, S1, S2, and S3 with `agent.model=gemini-3.8-flash`, real execution, exit code 0, verified output, and `GemminiRocketConfig`. The Gemini API returned HTTP 429 before S4 could be proposed. Raw evidence and the full Ray log are frozen on the VM and backed up to Google Drive with matching SHA256 hashes. See `docs/experiments/pilot-38-attempt-1-checkpoint.md`.

Attempt 1 is immutable and must not be combined with a future attempt. Do not start H1 main until one independent pilot attempt produces all five U0/S1/S2/S3/S4 rows and its evidence is frozen.

## Confirmed by execution evidence

- Upstream CHIA is pinned to commit `16c35e92aaaf9511c6453bf94cd5cf589698f4e3`; Gate A workflows use Python 3.10.19.
- Gate A.1 real CHIA smoke passes in GitHub Actions through `@ChiaFunction` + Ray, with `mocked=false`, `verification=PASS`, and uploaded evidence.
- Regular CI passes unit tests, local smoke, dry-run harness, safety challenge invariants, and shell entrypoint syntax validation.
- Gate A.2 preflight passes in GitHub Actions and uploads `gate-a2-preflight-evidence`. It validates the real CHIA cluster parser, worker resource topology, SafetyGate ALLOW decision, `GemminiRocketConfig`, and upstream `ChiselBuildNode.build` resource contract.

## Confirmed in-tree but NOT yet proven by real hardware execution

- `GeminiTypedActionAgent` uses a constrained structured-output schema; arbitrary parameter keys are not accepted.
- `GemminiChiselBuildExecutor` dispatches official `ChiselBuildNode` for `GemminiRocketConfig` and is explicitly non-mocked.
- H0 composes `ChiselBuildNode` + `RiscvBuildNode` + `VerilatorRunNode` and checks a marker.
- H1 uses upstream Gemmini `mvin_mvout-baremetal`, which exercises Gemmini memory movement and self-checks matrix equality.
- U0/S1/S2/S3/S4 semantics are explicit in `src/chia_work/variants.py`.
- S4 feedback/retry is implemented in `src/chia_work/agentic_loop.py` with complete attempt history.
- Counterfactual safety challenges never execute unsafe U0 actions.
- Real hardware pilot performs a setup warm-up excluded from comparative timing, then U0–S4 on the same incremental/cached environment.
- Environment capture records source revisions, Python/package versions and Docker IDs/digests.
- Cluster config exposes `chipyard`, `riscv_build`, and `verilator_run` workers.

## NOT yet proven by execution evidence

- A real `GemminiRocketConfig` Verilator simulator artifact has not yet been built and observed by us.
- H1 `mvin_mvout` has not yet produced a successful real Verilator result observed by us.
- Gemini → SafetyGate → H1 has not yet produced a successful full agentic accelerator artifact observed by us.
- Therefore **Gate A is OPEN and paper result cells remain empty**.

## Current isolation gates

```text
A.0 repo/control plane             PASS
A.1 real CHIA @ChiaFunction       PASS (mocked=false evidence)
A.2 preflight/contract             PASS (artifact uploaded)
A.2 real Gemmini simulator build  PENDING HOST EXECUTION
A.2b H1 mvin_mvout                PENDING
A.3 Gemini -> Safety -> H1         PENDING
```

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

## Exact next execution order

```bash
# Suitable Linux host with Docker + non-interactive self-SSH
bash scripts/bootstrap_chia.sh
bash scripts/preflight_gate_a2_host.sh
bash scripts/run_gate_a2_build.sh

# After A.2 real build passes
make real-gemmini-sanity
make real-gemmini-mvin-mvout

# After H1 passes
make real-agent-gemmini-mvin-mvout
make hardware-pilot
```

## Expected evidence files

```text
results/gate-a2-host-preflight.json
results/real-gemmini-build.jsonl
logs/gate-a2-gemmini-build.log
results/real-gemmini-sanity.jsonl
results/real-gemmini-mvin-mvout.jsonl
results/real-gemini-gemmini-mvin-mvout.jsonl
results/hardware-pilot-warmup.jsonl
results/hardware-pilot.jsonl
```

Real hardware/agent evidence must contain `mocked=false`. Unsafe safety-challenge cases are different: they are explicitly `counterfactual_only=true`, `executed=false`.

## Current external requirement

The remaining A.2 proof requires a suitable Linux host/VM with Docker, non-interactive SSH to the CHIA head/worker address, access to the CHIA GHCR images, and enough disk/RAM for Chipyard/Verilator. GitHub hosted CI is used only for the cheap A.2 contract preflight; it is not being treated as evidence of a real Gemmini build.

## Next after first H1 pass

1. Inspect pilot logs for integration mistakes only.
2. Freeze safety labels, recovery cases, repetitions and variant ordering on Sep 19.
3. Do not add another accelerator workload until the U0–S4 main table is complete.
4. Start writing paper architecture/method sections immediately; results remain TBD until real runs.
