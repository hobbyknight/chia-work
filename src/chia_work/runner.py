from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from .actions import TypedAction
from .safety import Decision, SafetyGate
from .structured_log import utc_now_iso


class ActionExecutor(Protocol):
    mocked: bool

    def execute(self, action: TypedAction) -> dict[str, Any]: ...


@dataclass
class RunResult:
    record: dict[str, Any]


class DryRunExecutor:
    """Plumbing-only executor. Its outputs are always marked mocked=true."""

    mocked = True

    def execute(self, action: TypedAction) -> dict[str, Any]:
        return {
            "backend": "dry-run",
            "status": "success",
            "exit_code": 0,
            "message": f"would execute {action.kind.value} on {action.target}",
            "verified": True,
        }


def run_action(
    action: TypedAction,
    *,
    variant: str,
    task_id: str,
    safety_enabled: bool,
    gate: SafetyGate | None = None,
    executor: ActionExecutor | None = None,
) -> RunResult:
    gate = gate or SafetyGate()
    executor = executor or DryRunExecutor()
    started = time.perf_counter()
    decision = gate.evaluate(action) if safety_enabled else None

    allowed = decision is None or decision.decision == Decision.ALLOW
    tool_result: dict[str, Any] | None = None
    if allowed:
        try:
            tool_result = executor.execute(action)
        except Exception as exc:  # preserve failed real runs as experiment evidence
            tool_result = {
                "backend": type(executor).__name__,
                "status": "error",
                "exit_code": 1,
                "verified": False,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }

    elapsed = time.perf_counter() - started
    if tool_result is None:
        verification = "NOT_RUN"
    elif tool_result.get("exit_code") == 0 and tool_result.get("verified", True):
        verification = "PASS"
    else:
        verification = "FAIL"

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
        "verification": verification,
        "retry_count": 0,
        "wall_time_seconds": elapsed,
        "mocked": bool(getattr(executor, "mocked", True)),
    }
    return RunResult(record)
