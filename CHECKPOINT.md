# CHECKPOINT

Snapshot: 2026-09-18 repository bootstrap.

## What is confirmed

- Dedicated repo exists and is writable.
- Short-term funded account has been confirmed by hackathon organizers for Sep 21–23.
- Official final deadline is Sep 24 AoE.
- Official final submission requires a 4-page paper and an open-sourced loop/results artifact.
- The local scaffold includes typed actions, a SafetyGate, JSONL logging, experiment config, and dry-run runner.

## What is NOT yet proven

- Official CHIA has not yet been installed by this repository bootstrap.
- No real Gemini API call has been executed from this repository.
- No real Gemmini/Chipyard build or simulation has been executed from this repository.
- No end-to-end real CHIA loop has been demonstrated.
- No paper result is available yet.

## Current gate

**Gate A: one real end-to-end path.**

Pass condition:

```text
real task/driver
  → typed action
  → SafetyGate decision
  → CHIA-backed real tool execution
  → verification
  → structured non-mocked log
```

Until this passes, all generated experiment outputs are scaffolding only.

## Immediate next actions

1. Run `scripts/bootstrap_chia.sh` on the development machine.
2. Inspect current official CHIA examples/APIs against the installed revision.
3. Select the smallest real Gemmini/Chipyard operation that can complete reliably.
4. Implement that operation in `src/chia_work/chia_adapter.py` or a dedicated tool adapter.
5. Replace dry-run execution for one action with the real backend.
6. Capture the first `mocked=false` JSONL record.
