from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from .actions import TypedAction
from .safety import Decision, SafetyGate
from .structured_log import utc_now_iso


@dataclass
class RunResult:
    record: dict[str, Any]


class DryRunExecutor:
    """Plumbing-only executor. Its outputs are always marked mocked=true."""

    def execute(self, action: TypedAction) -> dict[str, Any]:
        return {
            "backend": "dry-run",
            "status": "success",
            "exit_code": 0,
            "message": f"would execute {action.kind.value} on {action.target}",
        }


def run_action(
    action: TypedAction,
    *,
    variant: str,
    task_id: str,
    safety_enabled: bool,
    gate: SafetyGate | None = None,
) -> RunResult:
    gate = gate or SafetyGate()
    started = time.perf_counter()
    decision = gate.evaluate(action) if safety_enabled else None

    allowed = decision is None or decision.decision == Decision.ALLOW
    tool_result: dict[str, Any] | None = None
    if allowed:
        tool_result = DryRunExecutor().execute(action)

    elapsed = time.perf_counter() - started
    record = {
        "schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "timestamp_utc": utc_now_iso(),
        "variant": variant,
        "task_id": task_id,
        "action": action.to_dict(),
        "safety_enabled": safety_enabled,
        "safety_decision": None if decision is None else decision.decision.value,
        "safety_reason": None if decision is None else decision.reason,
        "tool_result": tool_result,
        "verification": "PASS" if tool_result and tool_result.get("exit_code") == 0 else "NOT_RUN",
        "retry_count": 0,
        "wall_time_seconds": elapsed,
        "mocked": True,
    }
    return RunResult(record)
