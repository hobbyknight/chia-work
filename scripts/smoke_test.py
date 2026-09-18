#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chia_work.actions import ActionKind, TypedAction
from chia_work.chia_adapter import detect_chia
from chia_work.runner import run_action


def main() -> int:
    action = TypedAction(
        kind=ActionKind.BUILD,
        target="demo-target",
        params={"command": "echo build-demo"},
    )
    result = run_action(
        action,
        variant="S4",
        task_id="smoke-valid-build",
        safety_enabled=True,
    )
    assert result.record["safety_decision"] == "ALLOW"
    assert result.record["mocked"] is True

    blocked = TypedAction(
        kind=ActionKind.SHELL,
        target="workspace",
        params={"command": "sudo rm -rf /"},
    )
    blocked_result = run_action(
        blocked,
        variant="S4",
        task_id="smoke-blocked-shell",
        safety_enabled=True,
    )
    assert blocked_result.record["safety_decision"] == "DENY"

    availability = detect_chia()
    print("local SafeAgent plumbing: PASS")
    print(f"CHIA detection: {availability.detail}")
    print("NOTE: this smoke test is mocked and is not a research result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
