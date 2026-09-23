"""Fixed child-process executor for the one exposed CHIA identity action."""

from __future__ import annotations

import json
import sys

from chia_work.actions import ActionKind, TypedAction
from chia_work.chia_adapter import execute_real_action
from chia_work.safety import Decision, SafetyGate
from chia_work.bridge.council_chia_bridge import BridgeValidationError, validate_request


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        validate_request(payload)
        raw = payload["execution_request"]["typed_action"]
        if raw.get("action_kind") != ActionKind.RUN_BENCHMARK.value or raw.get("target") != "chia-local-smoke":
            raise BridgeValidationError("child executor received action outside fixed safe surface")
        typed = TypedAction(ActionKind(raw["action_kind"]), raw["target"], dict(raw.get("payload", {})))
        decision = SafetyGate().evaluate(typed)
        if decision.decision != Decision.ALLOW:
            print(json.dumps({"status": "REJECTED", "backend": "safety-gate", "safety_decision": decision.decision.value, "reason": decision.reason, "hardware_executed": False}, sort_keys=True))
            return 0
        result = execute_real_action(typed)
        result["status"] = "EXECUTED" if result.get("status") == "success" else "REJECTED"
        result["hardware_executed"] = False
        result["safety_decision"] = decision.decision.value
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "EXECUTED" else 1
    except Exception as exc:
        print(json.dumps({"status": "REJECTED", "backend": "chia-child", "error_type": type(exc).__name__, "error": str(exc), "hardware_executed": False}, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
