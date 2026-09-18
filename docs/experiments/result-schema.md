# Result schema

Every JSONL record used in analysis should carry enough provenance to determine whether it is real, reproducible, and comparable.

## Required fields for real runs

```text
schema_version
run_id
timestamp_utc
variant
task_id
action
safety_enabled
safety_decision
safety_reason
backend
tool_result
verification
retry_count
wall_time_seconds
mocked
```

For real runs add, whenever available:

```text
model_id
prompt_id_or_hash
repo_commit
chia_commit
chipyard_commit
gemmini_commit
gcp_project_alias
machine_type
region
api_token_usage
api_cost
compute_cost
fault_id
seed
```

## Invariants

- Paper-quality rows require `mocked=false`.
- `run_id` must be unique.
- A failed/denied run is still a valid record and must not be deleted from raw logs.
- Analysis scripts may derive summary fields but must not mutate raw records.
- Secrets and raw credentials must never appear in logs.
