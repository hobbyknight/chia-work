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
    verification_enabled: bool = True,
) -> RunResult:
    gate = gate or SafetyGate()
    executor = executor or DryRunExecutor()
    started = time.perf_counter()

    gate_started = time.perf_counter()
    decision = gate.evaluate(action) if safety_enabled else None
    safety_gate_elapsed = time.perf_counter() - gate_started

    allowed = decision is None or decision.decision == Decision.ALLOW
    tool_result: dict[str, Any] | None = None
    executor_elapsed = 0.0
    if allowed:
        executor_started = time.perf_counter()
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
        finally:
            executor_elapsed = time.perf_counter() - executor_started

    elapsed = time.perf_counter() - started
    if not verification_enabled:
        verification = "DISABLED"
    elif tool_result is None:
        verification = "NOT_RUN"
    elif tool_result.get("exit_code") == 0 and tool_result.get("verified", True):
        verification = "PASS"
    else:
        verification = "FAIL"

    record = {
        "schema_version": 2,
        "run_id": str(uuid.uuid4()),
        "timestamp_utc": utc_now_iso(),
        "variant": variant,
        "task_id": task_id,
        "action": action.to_dict(),
        "safety_enabled": safety_enabled,
        "safety_decision": None if decision is None else decision.decision.value,
        "safety_reason": None if decision is None else decision.reason,
        "executed": tool_result is not None,
        "backend": None if tool_result is None else tool_result.get("backend"),
        "tool_result": tool_result,
        "verification_enabled": verification_enabled,
        "verification": verification,
        "retry_count": 0,
        # Kept for backward compatibility. This covers SafetyGate + executor,
        # not model proposal latency.
        "wall_time_seconds": elapsed,
        "action_wall_time_seconds": elapsed,
        "safety_gate_wall_time_seconds": safety_gate_elapsed,
        "executor_wall_time_seconds": executor_elapsed,
        "tool_call_count": 1 if tool_result is not None else 0,
        "mocked": bool(getattr(executor, "mocked", True)),
        # Never estimate monetary cost inside the execution harness.
        "api_cost_usd": None,
        "compute_cost_usd": None,
    }
    return RunResult(record)
