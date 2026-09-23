"""Validate-only Council-to-CHIA bridge.

The validate-only path intentionally contains no CHIA, Ray, Gemmini, Verilator,
subprocess, shell, or network execution. A future execution path must be added
behind the same deterministic checks and explicit authorization boundary.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from pydantic import ValidationError

from chia_work.council.schemas import DecisionRecord, ExecutionRequest, VetoRecord


FORBIDDEN_KEYS = {"bash", "commands", "exec", "executable", "rm", "shell", "ssh", "sudo"}
REQUIRED_EXECUTION_CAPABILITY = "REQUEST_EXECUTION"


class BridgeValidationError(ValueError):
    pass


def _reject_shell(value: Any, *, typed_action_payload: bool = False) -> None:
    if isinstance(value, dict):
        if FORBIDDEN_KEYS.intersection(value):
            raise BridgeValidationError("free-form shell command field is forbidden")
        if "command" in value:
            if not typed_action_payload or not isinstance(value["command"], str) or not value["command"].startswith("chia:"):
                raise BridgeValidationError("only a versioned chia operation may appear in typed_action payload")
        for key, item in value.items():
            _reject_shell(item, typed_action_payload=typed_action_payload or key == "payload")
    elif isinstance(value, list):
        for item in value:
            _reject_shell(item)


def validate_request(payload: dict[str, Any]) -> dict[str, Any]:
    _reject_shell(payload)
    try:
        request = ExecutionRequest.model_validate(payload["execution_request"])
        decision = DecisionRecord.model_validate(payload["decision_record"])
    except (KeyError, ValidationError) as exc:
        raise BridgeValidationError(f"invalid request or decision schema: {exc}") from exc
    if decision.id != request.decision_record_id:
        raise BridgeValidationError("decision_record_id mismatch")
    if decision.status != "APPROVED" or not decision.immutable:
        raise BridgeValidationError("execution requires an immutable APPROVED DecisionRecord")
    if decision.veto_refs:
        raise BridgeValidationError("active veto is present")
    grant = payload.get("capability_grant", {})
    if REQUIRED_EXECUTION_CAPABILITY not in grant.get("capabilities", []):
        raise BridgeValidationError("REQUEST_EXECUTION capability is not granted")
    action = request.typed_action
    if not isinstance(action.get("action_kind"), str) or not action["action_kind"]:
        raise BridgeValidationError("typed_action.action_kind is required")
    if not isinstance(action.get("payload", {}), dict):
        raise BridgeValidationError("typed_action.payload must be an object")
    return {
        "status": "VALIDATED",
        "execution_request_id": request.id,
        "decision_record_id": decision.id,
        "hardware_executed": False,
        "message": "validate-only passed; CHIA/Ray/Gemmini/Verilator were not called",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.validate_only:
        print(json.dumps({"status": "REJECTED", "error": "only --validate-only is implemented"}, sort_keys=True))
        return 2
    try:
        result = validate_request(json.load(sys.stdin))
    except (BridgeValidationError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
