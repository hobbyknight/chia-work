# CHIA + Gemmini integration plan

## Principle

Gate A should use the **smallest real operation** that proves the full control/data path. Do not begin with the largest Chipyard build.

## Upstream CHIA facts to verify against installed revision

- CHIA expresses workflows as graph/loop structures.
- Upstream exposes abstractions including `ChiaFunction` and `ChiaTool`.
- Upstream examples include build/simulator-oriented flows and cluster configuration.
- The official repository should be treated as the API source of truth; this repo must not vendor or silently fork CHIA during the sprint.

## Integration sequence

### I0 — CHIA import

`src/chia_work/chia_adapter.py` should detect/import the installed upstream package and record its revision/environment.

### I1 — One safe real tool

Wrap one deterministic, low-cost operation through CHIA. Required output:

```text
mocked=false
backend=chia
exit/status captured
verification captured
```

### I2 — Gemmini/Chipyard operation

Choose one operation with bounded runtime, for example a build/check/simulation/benchmark step already known to work in the local Gemmini/Chipyard environment.

The tool API should accept structured parameters rather than an unrestricted shell string.

### I3 — Agent proposal

Gemini (or the selected supported model path) proposes a typed action. The SafetyGate either allows, denies, or requests repair.

### I4 — Verification/recovery

After tool execution, parse outputs and enforce a task oracle. Feed failure evidence back to the agent with a retry cap.

## Gate A acceptance

A committed JSONL sample/log from an actual run exists with `mocked=false`, plus a command in README that another contributor can execute.
