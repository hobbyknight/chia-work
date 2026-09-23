from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from importlib import metadata
from typing import Any

from .actions import TypedAction
from .observability import ExecutionLifecycle


UPSTREAM_CHIA_COMMIT = "16c35e92aaaf9511c6453bf94cd5cf589698f4e3"


@dataclass(frozen=True)
class ChiaAvailability:
    available: bool
    detail: str


def detect_chia() -> ChiaAvailability:
    """Detect the upstream CHIA import and report the installed distribution."""
    try:
        from chia.base.ChiaFunction import ChiaFunction  # noqa: F401
    except Exception as exc:  # import/setup errors are useful during bootstrap
        return ChiaAvailability(False, f"CHIA import unavailable: {exc}")

    try:
        version = metadata.version("chialoops")
    except metadata.PackageNotFoundError:
        version = "unknown/editable"
    return ChiaAvailability(True, f"CHIA import succeeded (chialoops={version})")


def _canonical_action(action: TypedAction) -> str:
    return json.dumps(action.to_dict(), sort_keys=True, separators=(",", ":"))


class ChiaLocalExecutor:
    """Execute a deterministic action through a real CHIA ``ChiaFunction``.

    This executor deliberately does not invoke an arbitrary shell. Its purpose is
    Gate A.1: prove that SafeAgent can pass a typed action through SafetyGate,
    dispatch it through the real CHIA runtime, receive a worker result, verify
    the round trip, and emit a non-mocked record. The Gemmini/Chipyard executor
    is layered underneath the same runner next.
    """

    mocked = False

    def __init__(self, *, ray_address: str | None = None) -> None:
        self.ray_address = ray_address

    def execute(self, action: TypedAction) -> dict[str, Any]:
        import ray
        from chia.base.ChiaFunction import ChiaFunction, get

        if not ray.is_initialized():
            init_kwargs: dict[str, Any] = {
                "ignore_reinit_error": True,
                "include_dashboard": False,
                "log_to_driver": False,
            }
            if self.ray_address:
                init_kwargs["address"] = self.ray_address
            ray.init(**init_kwargs)

        expected_sha = hashlib.sha256(_canonical_action(action).encode("utf-8")).hexdigest()

        @ChiaFunction()
        def chia_identity_worker(payload: dict[str, Any]) -> dict[str, Any]:
            import hashlib as _hashlib
            import json as _json
            import os
            import socket

            canonical = _json.dumps(payload, sort_keys=True, separators=(",", ":"))
            observed_sha = _hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            return {
                "backend": "chia-ray",
                "status": "success",
                "exit_code": 0,
                "worker_hostname": socket.gethostname(),
                "worker_pid": os.getpid(),
                "observed_action_sha256": observed_sha,
                "received_action": payload,
            }

        lifecycle = ExecutionLifecycle.from_environment()
        lifecycle_errors: list[str] = []
        boundary_event = None

        def record_event(event_type: str, **fields):
            nonlocal boundary_event
            if lifecycle is None:
                return None
            try:
                event = lifecycle.append(event_type, **fields)
                if event_type == "execution_boundary_entered":
                    boundary_event = event
                return event
            except Exception as exc:
                lifecycle_errors.append(f"{type(exc).__name__}: {exc}")
                return None

        record_event(
            "execution_boundary_entered", phase="CHIA_EXECUTOR", status="ENTERED",
            execution_request_id=os.environ.get("SAFEAGENT_EXECUTION_REQUEST_ID"),
            action_sha256=expected_sha,
        )
        try:
            result = get(chia_identity_worker.chia_remote(action.to_dict()))
        except Exception as exc:
            record_event(
                "execution_failed", phase="CHIA_EXECUTOR", status="FAILED",
                execution_request_id=os.environ.get("SAFEAGENT_EXECUTION_REQUEST_ID"),
                boundary_event_id=None if boundary_event is None else boundary_event["event_id"],
                error_type=type(exc).__name__, error_message=str(exc),
            )
            # Preserve exception type and behavior while allowing structured callers to count entry.
            try:
                exc.execution_boundary_entered = True
                exc.execution_boundary_event_id = None if boundary_event is None else boundary_event["event_id"]
            except Exception:
                pass
            raise
        result["expected_action_sha256"] = expected_sha
        result["verified"] = result.get("observed_action_sha256") == expected_sha
        result["execution_boundary_entered"] = True
        result["execution_boundary_event_id"] = None if boundary_event is None else boundary_event["event_id"]
        result["upstream_chia_commit"] = UPSTREAM_CHIA_COMMIT
        try:
            result["chialoops_version"] = metadata.version("chialoops")
        except metadata.PackageNotFoundError:
            result["chialoops_version"] = "unknown/editable"
        if result["verified"]:
            record_event(
                "execution_completed", phase="CHIA_EXECUTOR", status="COMPLETED",
                execution_request_id=os.environ.get("SAFEAGENT_EXECUTION_REQUEST_ID"),
                boundary_event_id=None if boundary_event is None else boundary_event["event_id"],
                action_sha256=expected_sha,
            )
        else:
            record_event(
                "execution_failed", phase="VERIFIER", status="FAILED",
                execution_request_id=os.environ.get("SAFEAGENT_EXECUTION_REQUEST_ID"),
                boundary_event_id=None if boundary_event is None else boundary_event["event_id"],
                error_type="VerificationMismatch",
            )
        if lifecycle_errors:
            result["execution_lifecycle_errors"] = lifecycle_errors
        return result


def execute_real_action(action: TypedAction, *, ray_address: str | None = None) -> dict[str, Any]:
    """Compatibility helper for one real CHIA-dispatched typed action."""
    return ChiaLocalExecutor(ray_address=ray_address).execute(action)
