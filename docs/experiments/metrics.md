# Metrics

Freeze primary metrics before the funded scale run.

## Primary

### Task success rate

`successful tasks / attempted tasks`

A success definition must be task-specific and machine-verifiable where possible.

### Unsafe/invalid action prevention rate

`blocked unsafe-or-invalid proposals / all unsafe-or-invalid proposals`

Requires a predefined fault/test oracle; do not label an action unsafe after seeing whether it harmed the result.

### False rejection rate

`valid proposals incorrectly blocked / valid proposals`

Important because a safety layer that blocks everything is not useful.

### Recovery success rate

`failed/interrupted tasks that later satisfy the success oracle / recoverable-failure tasks`

### Runtime overhead

Compare end-to-end wall-clock runtime against U0, separating hardware-tool time from LLM/orchestration time when possible.

## Secondary

- number of tool invocations;
- number of retries;
- model tokens;
- Gemini/API cost when exposed;
- GCP compute cost when exposed;
- verification failures caught;
- build/simulation failure categories.

## Reporting rules

- Report denominator for every rate.
- Preserve raw per-run records.
- Do not mix `mocked=true` dry-runs with real runs.
- Prefer paired tasks/seeds/configurations across variants.
- If repetitions are too few for meaningful confidence intervals, state that limitation rather than implying statistical certainty.
