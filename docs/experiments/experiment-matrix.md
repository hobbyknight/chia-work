# Experiment matrix

Status: draft to freeze on Sep 19.

## Variants

| ID | Variant | Pre-check | Typed action | Post-check | Recovery loop |
|---|---|---:|---:|---:|---:|
| U0 | Unguarded agent baseline | No | No/weak | No | Agent-native only |
| S1 | Pre-execution validation | Yes | Weak | No | Limited |
| S2 | Typed actions | Yes | Yes | No | Limited |
| S3 | Typed + post-verification | Yes | Yes | Yes | Limited |
| S4 | Full SafeAgent | Yes | Yes | Yes | Yes, capped |

Exact implementation must be frozen before funded scale runs; do not move functionality between variants after seeing main results.

## Task families

Start with the smallest real workload that exercises the CHIA/Gemmini path reliably. Candidate families:

1. valid build/simulation task;
2. controlled config modification followed by build/sim;
3. benchmark execution and metric extraction;
4. injected malformed argument;
5. injected destructive/over-broad operation;
6. recoverable build or verification failure.

## Run identity

Every real run must record at least:

- `run_id`
- timestamp
- variant (`U0`–`S4`)
- task/fault ID
- prompt/input hash or stored prompt
- model identifier
- action proposal
- safety decision/reason
- backend/tool identifier
- command/config parameters after validation
- exit code/tool status
- verification result
- retries
- wall-clock runtime
- token/cost data when available
- git commit SHA and relevant upstream revision when available
- `mocked=false`

## Priority if compute is constrained

1. Complete the main table for U0 vs S4.
2. Add S1/S2/S3 ablations.
3. Add repetitions/confidence.
4. Add secondary task families.
5. Only then add new features.
