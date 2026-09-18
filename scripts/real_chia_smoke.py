#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chia_work.actions import ActionKind, TypedAction
from chia_work.chia_adapter import ChiaLocalExecutor, detect_chia
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gate A.1 through the real CHIA runtime")
    parser.add_argument("--output", default="results/real-chia-smoke.jsonl")
    parser.add_argument("--ray-address", default=None)
    args = parser.parse_args()

    availability = detect_chia()
    if not availability.available:
        raise SystemExit(availability.detail)

    action = TypedAction(
        kind=ActionKind.RUN_BENCHMARK,
        target="chia-local-smoke",
        params={
            "command": "chia:identity",
            "payload": "gate-a-real-chia-smoke",
        },
    )

    result = run_action(
        action,
        variant="S2-real-chia-smoke",
        task_id="gate-a-1-real-chia",
        safety_enabled=True,
        executor=ChiaLocalExecutor(ray_address=args.ray_address),
    )
    record = result.record

    if record["safety_decision"] != "ALLOW":
        raise RuntimeError(f"SafetyGate did not allow the smoke action: {record}")
    if record["mocked"] is not False:
        raise RuntimeError("Real CHIA smoke was incorrectly marked mocked")
    if record["verification"] != "PASS":
        raise RuntimeError(f"CHIA round-trip verification failed: {record}")
    if record["tool_result"].get("backend") != "chia-ray":
        raise RuntimeError(f"Unexpected backend: {record}")

    output = Path(args.output)
    append_jsonl(output, record)
    print(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False))
    print(f"Gate A.1 PASS: wrote non-mocked CHIA record to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
