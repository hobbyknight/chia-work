from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import metadata
from typing import Any

from .actions import TypedAction


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

        result = get(chia_identity_worker.chia_remote(action.to_dict()))
        result["expected_action_sha256"] = expected_sha
        result["verified"] = result.get("observed_action_sha256") == expected_sha
        result["upstream_chia_commit"] = UPSTREAM_CHIA_COMMIT
        try:
            result["chialoops_version"] = metadata.version("chialoops")
        except metadata.PackageNotFoundError:
            result["chialoops_version"] = "unknown/editable"
        return result


def execute_real_action(action: TypedAction, *, ray_address: str | None = None) -> dict[str, Any]:
    """Compatibility helper for one real CHIA-dispatched typed action."""
    return ChiaLocalExecutor(ray_address=ray_address).execute(action)
