"""Append-only execution lifecycle evidence for SafeAgent.

This module records events only. It does not authorize, reject, or modify actions.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COUNTER_NAMES = (
    "execution_requests_created",
    "execution_boundary_entries",
    "execution_completions",
    "execution_failures",
)
INTERVENTION_FIELDS = (
    "human_scientific_intervention_count",
    "chatgpt_scientific_intervention_count",
    "codex_scientific_intervention_count",
    "manual_gemini_output_repair_count",
    "manual_role_assignment_count",
    "manual_task_assignment_count",
    "manual_veto_override_count",
)


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class LifecycleIntegrityError(RuntimeError):
    """Raised when a lifecycle event stream is malformed or has a broken hash chain."""


class ExecutionLifecycle:
    """Durable, append-only event stream with counters derived from verified events."""

    def __init__(self, run_id: str, stream_path: str | Path):
        self.run_id = str(run_id)
        self.stream_path = Path(stream_path)
        self.lock_path = self.stream_path.with_suffix(self.stream_path.suffix + ".lock")
        self._persisted_refs: list[Any] | None = None

    @classmethod
    def from_environment(cls) -> "ExecutionLifecycle | None":
        stream_path = os.environ.get("SAFEAGENT_LIFECYCLE_PATH")
        run_id = os.environ.get("SAFEAGENT_RUN_ID")
        if not stream_path or not run_id:
            return None
        return cls(run_id, stream_path)

    def _load_verified(self) -> list[dict[str, Any]]:
        if not self.stream_path.exists():
            return []
        events: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        terminal_seen = False
        previous = None
        for sequence, line in enumerate(self.stream_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                raise LifecycleIntegrityError(f"empty event at sequence {sequence}")
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LifecycleIntegrityError(f"malformed event at sequence {sequence}") from exc
            required = {"schema_version", "event_id", "run_id", "sequence", "timestamp_utc", "event_type", "phase", "status", "previous_event_sha256"}
            if not required.issubset(event):
                raise LifecycleIntegrityError(f"missing required field at sequence {sequence}")
            if terminal_seen:
                raise LifecycleIntegrityError("event appears after terminal")
            digest = event.pop("event_sha256", None)
            if event.get("event_id") in seen_ids:
                raise LifecycleIntegrityError(f"duplicate event id at sequence {sequence}")
            seen_ids.add(event.get("event_id"))
            if event.get("event_type") == "terminal":
                terminal_seen = True
            if event.get("sequence") != sequence:
                raise LifecycleIntegrityError(f"sequence mismatch at {sequence}")
            if event.get("previous_event_sha256") != previous:
                raise LifecycleIntegrityError(f"previous hash mismatch at {sequence}")
            expected = hashlib.sha256(_canonical(event)).hexdigest()
            if digest != expected:
                raise LifecycleIntegrityError(f"event hash mismatch at {sequence}")
            event["event_sha256"] = digest
            if event.get("run_id") != self.run_id:
                raise LifecycleIntegrityError(f"run id mismatch at {sequence}")
            events.append(event)
            previous = digest
        return events

    def append(self, event_type: str, *, phase: str, status: str, **fields: Any) -> dict[str, Any]:
        self.stream_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            events = self._load_verified()
            terminal_exists = any(e["event_type"] == "terminal" for e in events)
            if terminal_exists:
                raise LifecycleIntegrityError("cannot append after terminal lifecycle event")
            previous = events[-1]["event_sha256"] if events else None
            event = {
                "schema_version": 1,
                "event_id": f"{self.run_id}:event:{len(events) + 1}",
                "run_id": self.run_id,
                "sequence": len(events) + 1,
                "timestamp_utc": _utc_now(),
                "event_type": event_type,
                "phase": phase,
                "status": status,
                "previous_event_sha256": previous,
                **fields,
            }
            digest = hashlib.sha256(_canonical(event)).hexdigest()
            encoded = _canonical({**event, "event_sha256": digest}) + b"\n"
            fd = os.open(self.stream_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                written = os.write(fd, encoded)
                if written != len(encoded):
                    raise OSError("short append while writing lifecycle event")
                os.fsync(fd)
            finally:
                os.close(fd)
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            return {**event, "event_sha256": digest}

    def events(self) -> list[dict[str, Any]]:
        return self._load_verified()

    def counters(self) -> dict[str, int]:
        events = self.events()
        return {
            "execution_requests_created": sum(e["event_type"] == "execution_request_created" for e in events),
            "execution_boundary_entries": sum(e["event_type"] == "execution_boundary_entered" for e in events),
            "execution_completions": sum(e["event_type"] == "execution_completed" for e in events),
            "execution_failures": sum(e["event_type"] == "execution_failed" for e in events),
        }

    def terminal_event(self) -> dict[str, Any] | None:
        return next((e for e in reversed(self.events()) if e["event_type"] == "terminal"), None)

    def terminal(self, terminal_status: str, terminal_phase: str, reason: str, **references: Any) -> dict[str, Any]:
        existing = self.terminal_event()
        if existing is not None:
            return existing
        counts = self.counters()
        return self.append(
            "terminal",
            phase=terminal_phase,
            status=terminal_status,
            terminal_status=terminal_status,
            terminal_phase=terminal_phase,
            reason=reason,
            execution_boundary_entered=counts["execution_boundary_entries"] > 0,
            counters=counts,
            references=references,
        )

    def persist(self, store: Any, *, creator: str = "safeagent-observability") -> list[Any]:
        if self._persisted_refs is not None:
            return list(self._persisted_refs)
        events = self.events()
        if not events:
            self.append("run_started", phase="INITIALIZATION", status="STARTED")
            events = self.events()
        run_id = self.run_id
        cycle_id = str(next((e.get("cycle_id") for e in events if e.get("cycle_id")), run_id))
        event_text = self.stream_path.read_text(encoding="utf-8")
        event_digest = hashlib.sha256(event_text.encode("utf-8")).hexdigest()
        event_ref = store.write_text(
            "lifecycle/events.jsonl", event_text,
            artifact_id=f"{run_id}:lifecycle-events", cycle_id=cycle_id, creator=creator,
            kind="lifecycle-jsonl",
        )
        counters = self.counters()
        counters_ref = store.write_json(
            "lifecycle/execution-counters.json",
            {"schema_version": 1, "run_id": run_id, "cycle_id": cycle_id,
             **counters, "events_sha256": event_digest, "events_artifact_id": event_ref.id},
            artifact_id=f"{run_id}:execution-counters", cycle_id=cycle_id, creator=creator,
            parent_id=event_ref.id, lineage_refs=[event_ref.id],
        )
        zero_snapshot = {field: 0 for field in INTERVENTION_FIELDS}
        intervention_ref = store.write_json(
            "lifecycle/intervention-snapshot.json",
            {"schema_version": 1, "run_id": run_id, "cycle_id": cycle_id,
             "counts": zero_snapshot,
             "measurement_source": "explicit default zero; no production increment site exists for these fields",
             "not_measured_claim": True},
            artifact_id=f"{run_id}:intervention-snapshot", cycle_id=cycle_id, creator=creator,
            parent_id=event_ref.id, lineage_refs=[event_ref.id],
        )
        refs = [event_ref, counters_ref, intervention_ref]
        terminal = self.terminal_event()
        if terminal is not None:
            terminal_ref = store.write_json(
                "lifecycle/terminal.json", terminal,
                artifact_id=f"{run_id}:terminal", cycle_id=cycle_id, creator=creator,
                parent_id=event_ref.id, lineage_refs=[event_ref.id],
            )
            refs.append(terminal_ref)
        self._persisted_refs = refs
        return list(refs)


def validate_lifecycle_artifacts(root: str | Path, run_id: str) -> dict[str, Any]:
    """Validate an indexed lifecycle artifact set and its event-derived counters."""
    from .council.artifacts import ArtifactStore

    root = Path(root)
    store = ArtifactStore(root)
    refs = store.all_refs()
    if not refs or not all(store.verify(ref) for ref in refs):
        raise LifecycleIntegrityError("artifact index contains a missing or hash-mismatched artifact")
    stream = root / "lifecycle" / "events.jsonl"
    temp_lifecycle = ExecutionLifecycle(run_id, stream)
    events = temp_lifecycle.events()
    counters = json.loads((root / "lifecycle" / "execution-counters.json").read_text(encoding="utf-8"))
    expected = temp_lifecycle.counters()
    if any(counters.get(name) != value for name, value in expected.items()):
        raise LifecycleIntegrityError("execution counter snapshot does not match event stream")
    interventions = json.loads((root / "lifecycle" / "intervention-snapshot.json").read_text(encoding="utf-8"))
    if set(interventions.get("counts", {})) != set(INTERVENTION_FIELDS):
        raise LifecycleIntegrityError("intervention snapshot field set mismatch")
    if any(interventions["counts"].get(name) != 0 for name in INTERVENTION_FIELDS):
        raise LifecycleIntegrityError("unmeasured intervention fields must remain explicitly zero")
    terminal = next((event for event in reversed(events) if event["event_type"] == "terminal"), None)
    terminal_path = root / "lifecycle" / "terminal.json"
    if terminal is None or not terminal_path.exists() or json.loads(terminal_path.read_text(encoding="utf-8")) != terminal:
        raise LifecycleIntegrityError("terminal lifecycle artifact missing or inconsistent")
    return {"valid": True, "run_id": run_id, "event_count": len(events), "counters": expected, "artifact_count": len(refs)}
