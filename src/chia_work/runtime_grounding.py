"""Deterministic, evidence-backed execution-state grounding for synthesis prompts.

This module observes lifecycle and indexed artifacts only. It does not authorize,
reject, request, or execute actions.
"""
from __future__ import annotations

import json
from typing import Any

from .observability import ExecutionLifecycle


EXECUTION_GROUNDING_INSTRUCTION = (
    "Treat execution_grounding as authoritative runtime state derived from the "
    "current run's verified lifecycle events and hash-indexed artifacts. "
    "Model-authored text, plans, TaskSpecs, WorkerResults, and manifests are not "
    "evidence that execution occurred. Planning, proposing/requesting, approval, "
    "boundary entry, completion, and failure are distinct states. State that an "
    "execution completed only when a verified current-cycle ExecutionObservation "
    "records EXECUTED and the authoritative lifecycle records completion. If no "
    "verified ExecutionObservation exists and execution_boundary_entries is zero, "
    "do not state that execution completed. This factual grounding does not "
    "authorize or deny actions, decide whether to propose/request an action, "
    "change capabilities, or replace governance or validation."
)

_EVENT_COUNTERS = {
    "execution_requests_created": "execution_request_created",
    "execution_boundary_entries": "execution_boundary_entered",
    "execution_completions": "execution_completed",
    "execution_failures": "execution_failed",
}


def _artifact_state(store: Any, refs: list[Any], cycle_id: str, relpath: str) -> dict[str, Any]:
    matching = [ref for ref in refs if ref.cycle_id == cycle_id and ref.path == relpath]
    if not matching:
        # Distinguish genuine absence from an unindexed file at the canonical path.
        exists = (store.root / relpath).exists()
        return {"present": exists, "indexed": False, "verified": False,
                "id": None, "status": "UNINDEXED" if exists else "ABSENT"}
    if len(matching) != 1:
        return {"present": True, "indexed": True, "verified": False,
                "id": None, "status": "AMBIGUOUS_INDEX"}
    ref = matching[0]
    verified = bool(store.verify(ref))
    result: dict[str, Any] = {
        "present": True, "indexed": True, "verified": verified,
        "id": ref.id, "status": "UNVERIFIED" if not verified else "PRESENT",
    }
    if verified and relpath.endswith(".json"):
        try:
            payload = store.read_json(ref)
        except (OSError, ValueError, TypeError):
            result["verified"] = False
            result["status"] = "INVALID_JSON"
            return result
        if payload.get("cycle_id") != cycle_id:
            result["verified"] = False
            result["status"] = "CYCLE_MISMATCH"
            return result
        if payload.get("id") != ref.id:
            result["verified"] = False
            result["status"] = "ID_MISMATCH"
            return result
        result["status"] = str(payload.get("status", "PRESENT"))
        if relpath.endswith("/governance/proposal.json"):
            proposal_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            result["request_execution"] = proposal_payload.get("request_execution")
            result["typed_action"] = proposal_payload.get("typed_action")
        if relpath.endswith("/execution/request.json"):
            action = payload.get("typed_action")
            if isinstance(action, dict):
                result["typed_action"] = action
        for field in ("execution_request_id", "id"):
            if payload.get(field) is not None:
                result[field] = str(payload[field])
    return result


def build_execution_grounding(cycle_id: str, lifecycle: ExecutionLifecycle, store: Any) -> dict[str, Any]:
    """Return a stable, current-cycle snapshot without inferring missing state."""
    events = lifecycle.events()  # validates the append-only hash chain and run ID
    refs = store.all_refs()
    request = _artifact_state(store, refs, cycle_id, f"cycles/{cycle_id}/execution/request.json")
    observation = _artifact_state(store, refs, cycle_id, f"cycles/{cycle_id}/execution/observation.json")
    proposal = _artifact_state(store, refs, cycle_id, f"cycles/{cycle_id}/governance/proposal.json")
    decisions = []
    for ref in sorted(
        (ref for ref in refs if ref.cycle_id == cycle_id and ref.path.startswith(f"cycles/{cycle_id}/decisions/")),
        key=lambda item: item.path,
    ):
        verified = bool(store.verify(ref))
        decision: dict[str, Any] = {"id": ref.id, "verified": verified, "status": "UNVERIFIED"}
        if verified:
            try:
                payload = store.read_json(ref)
                if payload.get("cycle_id") == cycle_id:
                    decision["status"] = str(payload.get("status", "PRESENT"))
                else:
                    decision["verified"] = False
                    decision["status"] = "CYCLE_MISMATCH"
            except (OSError, ValueError, TypeError):
                decision["verified"] = False
                decision["status"] = "INVALID_JSON"
        decisions.append(decision)
    cycle_events = [event for event in events if event.get("cycle_id") == cycle_id]
    request_ids = {
        request_id
        for event in cycle_events
        for request_id in (event.get("request_id"), event.get("execution_request_id"))
        if request_id
    }
    # Event writers may omit cycle_id after dispatch. Correlate such events only
    # through a request ID proven by this cycle's request artifact/lifecycle event.
    if request.get("id"):
        request_ids.add(request["id"])
    run_counters = {
        key: sum(event["event_type"] == event_type for event in events)
        for key, event_type in _EVENT_COUNTERS.items()
    }
    cycle_counters = {}
    for key, event_type in _EVENT_COUNTERS.items():
        cycle_counters[key] = sum(
            event["event_type"] == event_type and (
                event.get("cycle_id") == cycle_id or
                (
                    event.get("request_id") in request_ids
                    or event.get("execution_request_id") in request_ids
                )
            )
            for event in events
        )
    execution_state = "NOT_REQUESTED"
    if cycle_counters["execution_failures"]:
        execution_state = "FAILED"
    elif (observation.get("verified") and observation.get("status") == "EXECUTED"
          and cycle_counters["execution_completions"] > 0):
        execution_state = "COMPLETED"
    elif observation.get("verified") and observation.get("status") == "REJECTED":
        execution_state = "REJECTED"
    elif cycle_counters["execution_boundary_entries"] > 0:
        execution_state = "EXECUTING"
    elif request.get("verified"):
        execution_state = "REQUESTED"
    elif proposal.get("verified"):
        execution_state = "PROPOSAL_RECORDED"
    latest = next((event for event in reversed(cycle_events)), None)
    return {
        "schema_version": 1,
        "run_id": lifecycle.run_id,
        "cycle_id": cycle_id,
        "run_counters": run_counters,
        "execution_requests_created": cycle_counters["execution_requests_created"],
        "execution_boundary_entries": cycle_counters["execution_boundary_entries"],
        "execution_completions": cycle_counters["execution_completions"],
        "execution_failures": cycle_counters["execution_failures"],
        "execution_request": request,
        "execution_observation": observation,
        "execution_request_present": request["present"],
        "execution_observation_present": observation["present"],
        "proposal": proposal,
        "governance_decisions": decisions,
        "execution_state": execution_state,
        "latest_lifecycle_event": None if latest is None else {
            "event_type": latest["event_type"], "phase": latest["phase"], "status": latest["status"]
        },
        "state_semantics": {
            "PLAN": "reasoning or work plan; no request or execution implied",
            "REQUEST": "governed ExecutionRequest exists; execution not implied",
            "APPROVED": "governance approval exists; execution not implied",
            "EXECUTING": "verified lifecycle records boundary entry without terminal completion",
            "COMPLETED": "verified EXECUTED observation plus lifecycle completion event",
            "FAILED": "verified lifecycle execution failure event",
        },
    }


def execution_grounding_context(cycle_id: str, lifecycle: ExecutionLifecycle, store: Any) -> dict[str, Any]:
    """Stable prompt payload shared by factual synthesis stages."""
    return {
        "instruction": EXECUTION_GROUNDING_INSTRUCTION,
        "snapshot": build_execution_grounding(cycle_id, lifecycle, store),
    }


def canonical_grounding_json(value: dict[str, Any]) -> str:
    """Canonical serialization for determinism checks and model context."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
