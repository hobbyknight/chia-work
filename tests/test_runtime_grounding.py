import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from chia_work.council.artifacts import ArtifactStore
from chia_work.observability import ExecutionLifecycle
from chia_work.runtime_grounding import (
    EXECUTION_GROUNDING_INSTRUCTION,
    build_execution_grounding,
    canonical_grounding_json,
    execution_grounding_context,
)


def _state(tmp_path, run_id="run-a", cycle_id="cycle-a"):
    root = tmp_path / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root, ExecutionLifecycle(run_id, root / ".lifecycle-events.jsonl"), ArtifactStore(root)


def _write(store, cycle_id, kind, status):
    path = f"cycles/{cycle_id}/execution/{kind}.json"
    ident = f"{cycle_id}:{kind}"
    payload = {"schema_version": 1, "id": ident, "cycle_id": cycle_id, "status": status}
    if kind == "observation":
        payload["execution_request_id"] = f"{cycle_id}:request"
    store.write_json(path, payload, artifact_id=ident, cycle_id=cycle_id, creator="test")


def test_zero_state_and_missing_artifacts_are_explicit(tmp_path):
    _, life, store = _state(tmp_path)
    snapshot = build_execution_grounding("cycle-a", life, store)
    assert snapshot["execution_requests_created"] == 0
    assert snapshot["execution_boundary_entries"] == 0
    assert snapshot["execution_completions"] == 0
    assert snapshot["execution_failures"] == 0
    assert snapshot["execution_request_present"] is False
    assert snapshot["execution_observation_present"] is False
    assert snapshot["execution_observation"]["status"] == "ABSENT"
    assert snapshot["execution_state"] == "NOT_REQUESTED"


def test_request_without_observation_is_only_requested(tmp_path):
    _, life, store = _state(tmp_path)
    _write(store, "cycle-a", "request", "REQUESTED")
    life.append("execution_request_created", phase="REQUEST", status="REQUESTED", cycle_id="cycle-a", request_id="cycle-a:request")
    snapshot = build_execution_grounding("cycle-a", life, store)
    assert snapshot["execution_requests_created"] == 1
    assert snapshot["execution_request_present"] is True
    assert snapshot["execution_observation_present"] is False
    assert snapshot["execution_state"] == "REQUESTED"


def test_boundary_without_completion_is_not_completed(tmp_path):
    _, life, store = _state(tmp_path)
    _write(store, "cycle-a", "request", "REQUESTED")
    life.append("execution_request_created", phase="REQUEST", status="REQUESTED", cycle_id="cycle-a", request_id="cycle-a:request")
    life.append("execution_boundary_entered", phase="CHIA_EXECUTOR", status="ENTERED", execution_request_id="cycle-a:request")
    snapshot = build_execution_grounding("cycle-a", life, store)
    assert snapshot["execution_boundary_entries"] == 1
    assert snapshot["execution_completions"] == 0
    assert snapshot["execution_state"] == "EXECUTING"


def test_success_requires_observation_and_completion_event(tmp_path):
    _, life, store = _state(tmp_path)
    _write(store, "cycle-a", "request", "REQUESTED")
    _write(store, "cycle-a", "observation", "EXECUTED")
    for event, phase, status in [
        ("execution_request_created", "REQUEST", "REQUESTED"),
        ("execution_boundary_entered", "CHIA_EXECUTOR", "ENTERED"),
        ("execution_completed", "CHIA_EXECUTOR", "COMPLETED"),
    ]:
        fields = {"cycle_id": "cycle-a", "request_id": "cycle-a:request"} if event == "execution_request_created" else {"execution_request_id": "cycle-a:request"}
        life.append(event, phase=phase, status=status, **fields)
    snapshot = build_execution_grounding("cycle-a", life, store)
    assert snapshot["execution_observation"]["verified"] is True
    assert snapshot["execution_observation"]["status"] == "EXECUTED"
    assert snapshot["execution_completions"] == 1
    assert snapshot["execution_state"] == "COMPLETED"


def test_failure_with_observation_is_failed_not_completed(tmp_path):
    _, life, store = _state(tmp_path)
    _write(store, "cycle-a", "request", "REQUESTED")
    _write(store, "cycle-a", "observation", "REJECTED")
    life.append("execution_request_created", phase="REQUEST", status="REQUESTED", cycle_id="cycle-a", request_id="cycle-a:request")
    life.append("execution_boundary_entered", phase="CHIA_EXECUTOR", status="ENTERED", execution_request_id="cycle-a:request")
    life.append("execution_failed", phase="CHIA_EXECUTOR", status="FAILED", execution_request_id="cycle-a:request")
    snapshot = build_execution_grounding("cycle-a", life, store)
    assert snapshot["execution_failures"] == 1
    assert snapshot["execution_state"] == "FAILED"


def test_counters_are_derived_from_verified_lifecycle(tmp_path):
    _, life, store = _state(tmp_path)
    for event, phase, status in [
        ("execution_request_created", "REQUEST", "REQUESTED"),
        ("execution_boundary_entered", "EXECUTION", "ENTERED"),
        ("execution_failed", "EXECUTION", "FAILED"),
    ]:
        life.append(event, phase=phase, status=status, cycle_id="cycle-a", request_id="r1")
    snapshot = build_execution_grounding("cycle-a", life, store)
    assert snapshot["execution_requests_created"] == 1
    assert snapshot["execution_boundary_entries"] == 1
    assert snapshot["execution_completions"] == 0
    assert snapshot["execution_failures"] == 1
    assert snapshot["run_counters"] == life.counters()


def test_unindexed_canonical_artifact_is_not_claimed_verified(tmp_path):
    root, life, store = _state(tmp_path)
    path = root / "cycles/cycle-a/execution/observation.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"cycle_id": "cycle-a", "status": "EXECUTED"}))
    snapshot = build_execution_grounding("cycle-a", life, store)
    assert snapshot["execution_observation_present"] is True
    assert snapshot["execution_observation"]["status"] == "UNINDEXED"
    assert snapshot["execution_state"] != "COMPLETED"


def test_old_cycle_events_do_not_leak_into_current_cycle_counts(tmp_path):
    _, life, store = _state(tmp_path)
    life.append("execution_request_created", phase="REQUEST", status="REQUESTED", cycle_id="old-cycle", request_id="old-request")
    life.append("execution_boundary_entered", phase="EXECUTION", status="ENTERED", cycle_id="old-cycle", request_id="old-request")
    snapshot = build_execution_grounding("cycle-a", life, store)
    assert snapshot["run_counters"]["execution_boundary_entries"] == 1
    assert snapshot["execution_boundary_entries"] == 0
    assert snapshot["execution_state"] == "NOT_REQUESTED"


def test_previous_run_observation_does_not_leak_into_new_run(tmp_path):
    _, _, old_store = _state(tmp_path, "old-run")
    _write(old_store, "cycle-a", "observation", "EXECUTED")
    _, new_life, new_store = _state(tmp_path, "new-run")
    snapshot = build_execution_grounding("cycle-a", new_life, new_store)
    assert snapshot["execution_observation_present"] is False
    assert snapshot["execution_state"] == "NOT_REQUESTED"


def test_grounding_serialization_is_deterministic(tmp_path):
    _, life, store = _state(tmp_path)
    life.append("cycle_started", phase="HIERARCHY", status="OPEN", cycle_id="cycle-a")
    first = execution_grounding_context("cycle-a", life, store)
    second = execution_grounding_context("cycle-a", life, store)
    assert canonical_grounding_json(first) == canonical_grounding_json(second)


@pytest.mark.parametrize("workers", [1, 2, 4, 8])
def test_concurrent_snapshot_reads_are_stable(tmp_path, workers):
    _, life, store = _state(tmp_path)
    life.append("cycle_started", phase="HIERARCHY", status="OPEN", cycle_id="cycle-a")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        values = list(pool.map(lambda _: canonical_grounding_json(build_execution_grounding("cycle-a", life, store)), range(16)))
    assert len(set(values)) == 1


def test_instruction_distinguishes_execution_states_without_refusal_policy(tmp_path):
    _, life, store = _state(tmp_path, "semantic-state-run")
    states = build_execution_grounding("cycle-a", life, store)["state_semantics"]
    assert set(states) == {"PLAN", "REQUEST", "APPROVED", "EXECUTING", "COMPLETED", "FAILED"}
    assert len(set(states.values())) == len(states)
    normalized = EXECUTION_GROUNDING_INSTRUCTION.lower()
    assert "does not authorize or deny actions" in normalized
    assert "decide whether to propose/request an action" in normalized
    assert "never execute chia" not in normalized
    assert "request_execution=false" not in normalized
    assert "do not request execution" not in normalized


def test_zero_boundary_and_absent_observation_cannot_be_completed(tmp_path):
    _, life, store = _state(tmp_path)
    snapshot = build_execution_grounding("cycle-a", life, store)
    serialized = canonical_grounding_json(snapshot)
    assert '"execution_boundary_entries":0' in serialized
    assert '"execution_observation_present":false' in serialized
    assert '"execution_state":"COMPLETED"' not in serialized
    assert "only when a verified current-cycle ExecutionObservation" in EXECUTION_GROUNDING_INSTRUCTION
