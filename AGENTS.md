# AGENTS.md — Project operating rules

These instructions apply to ChatGPT, Codex, Gemini, Claude, and human contributors working in this repository.

## Before changing anything

1. Read `README.md`, `CURRENT-PLAN.md`, `CHECKPOINT.md`, and `PACKAGE-STATUS.md`.
2. Read `docs/experiments/experiment-matrix.md` before adding experiments.
3. Do not silently expand scope after the experiment matrix is frozen.
4. Preserve existing work; prefer small reviewable changes over broad rewrites.

## Scientific integrity

- Never invent experiment results, costs, success rates, timing numbers, or CHIA/Gemmini execution evidence.
- Synthetic/dry-run data must carry `mocked=true` and must never enter paper result tables.
- A result is real only when its log records the actual backend/tool, configuration, commit SHA (when available), and exit status.
- Separate implementation bugs from agent failures and infrastructure failures.

## Safety and secrets

- Never commit API keys, GCP service-account JSON, access tokens, passwords, or private URLs.
- Use `.env.example` for variable names only.
- New GCP credentials must be injected at runtime, never hard-coded.
- The current `SafetyGate` is an experimental policy layer, not a production sandbox or security boundary.

## Definition of done

A feature is not done until it has:

1. a reproducible invocation;
2. explicit failure handling;
3. structured logging;
4. a verification step or test;
5. documentation sufficient for another person to rerun it.

## Hackathon priority order

1. End-to-end runnable loop.
2. Reproducible experiments.
3. Main-table completeness.
4. Paper + public artifact.
5. Nice-to-have features.

If time is tight, cut scope rather than weaken reproducibility.
