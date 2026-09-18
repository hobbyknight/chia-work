# Experiment matrix

Status: implementation-defined on Sep 18; freeze candidate for Sep 19 after the first real pilot.

## Exact variants

The code-level source of truth is `src/chia_work/variants.py`. Functionality must not move between variants after main-result inspection.

| ID | Pre-execution safety | Target-specific semantic policy | Post-execution verification used by system | Feedback repair/retry |
|---|---:|---:|---:|---:|
| U0 | No | No | No | No |
| S1 | Yes, generic type/command checks | No | No | No |
| S2 | Yes | Yes | No | No |
| S3 | Yes | Yes | Yes | No |
| S4 | Yes | Yes | Yes | Yes, max 2 retries by default |

Important evaluation distinction: U0-S2 do not consume the post-execution oracle inside the system, but the experiment evaluator may still use ground-truth outcome afterward to compute task success. This avoids hiding failures from the paper while preserving the ablation semantics.

## Main real hardware workload

### H1 — Gemmini `mvin_mvout`

Target: `GemminiRocketConfig` under CHIA/Chipyard Verilator.

Pipeline:

```text
Gemini proposal
  -> TypedAction
  -> variant policy
  -> CHIA ChiselBuildNode(GemminiRocketConfig)
  -> upstream gemmini-rocc-tests mvin_mvout-baremetal
  -> CHIA VerilatorRunNode
  -> upstream self-checking exit status
```

`mvin_mvout` invokes Gemmini DMA operations to move matrices into the accelerator scratchpad and back to main memory. The upstream test compares input/output matrices and exits non-zero on mismatch. Therefore successful simulator exit is an objective oracle rather than a model-judged result.

Implementation: `src/chia_work/gemmini_mvin_mvout.py`.

Pilot manifest: `configs/hardware-pilot.json`.

## Bring-up hardware workload

### H0 — Gemmini sanity ELF

A small bare-metal ELF prints `SAFEAGENT_GEMMINI_SANITY_PASS`. It validates CHIA build/compile/run plumbing but does not exercise Gemmini accelerator instructions. H0 is infrastructure evidence only and must not be presented as the primary accelerator workload.

Implementation: `src/chia_work/gemmini_sanity.py`.

## Safety challenge suite

Safety challenges are counterfactual and **never execute the proposed action**. This is especially important for U0: the evaluator records that U0 *would execute* an unsafe proposal instead of actually issuing destructive commands or wasting compute.

Current suite: `configs/safety-challenges.json`.

Case families include:

1. disallowed shell action;
2. destructive command fragments;
3. shell chaining/metacharacters;
4. invalid Gemmini configuration;
5. excessive build parallelism;
6. untrusted Gemmini test checkout path;
7. excessive simulation-cycle budget;
8. known-valid Gemmini build (false-rejection control);
9. known-valid `mvin_mvout` workload (false-rejection control).

Primary safety metrics from this suite:

- unsafe/invalid action prevention rate;
- repair-request rate where the proposal is recoverable;
- false rejection rate on known-valid actions;
- policy classification accuracy against the frozen case labels.

## Recovery evaluation

S4's implementation is `src/chia_work/agentic_loop.py`.

When a proposal is `DENY`/`REPAIR`, the exact SafetyGate feedback is returned to Gemini. When an executed action fails verification, the observed tool result is returned instead. Gemini may propose a corrected action up to the configured retry cap. Records preserve complete `attempt_history`, `retry_count`, and `recovered`.

Recovery tasks should be frozen before scale runs and should include both:

- pre-execution repair (e.g. excessive resource budget or invalid config);
- post-execution repair (a controlled workload/tool failure with an objective oracle).

## Pilot methodology

`configs/hardware-pilot.json` and `scripts/run_real_hardware_pilot.py` perform one setup warm-up excluded from comparative timing, then run U0-S4 against the same cached/incremental `mvin_mvout` environment. This avoids charging every variant for an identical first-time Verilator build.

The pilot is for integration/failure discovery. Main results require frozen repetitions and, where feasible, randomized/interleaved variant order to reduce temporal/cache bias.

## Run identity and provenance

Every real run must record at least:

- `run_id`, timestamp, suite, variant, repetition;
- task/fault ID;
- prompt/model and token metadata;
- full typed action proposal;
- safety decision/reason;
- executor/backend;
- exit code/tool status;
- verification mode/result;
- retry/attempt history;
- wall-clock runtime;
- `mocked=false`;
- source/binary hashes when applicable.

Before experimental batches, run `scripts/capture_environment.py` to save:

- `chia-work` commit + dirty state;
- pinned upstream CHIA revision;
- Python/package versions;
- Docker image IDs/digests for Chisel build, RISC-V cross compiler and Verilator workers.

## Priority if compute is constrained

1. Real H1 path passes once.
2. U0 vs S4 main task-success comparison.
3. Safety challenge suite + S4 recovery cases.
4. S1/S2/S3 ablations.
5. Repetitions/confidence intervals.
6. Additional Gemmini workloads only if the main table is complete.
