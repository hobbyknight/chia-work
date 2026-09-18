#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from chia_work.actions import ActionKind, TypedAction
from chia_work.gemmini_adapter import GemminiChiselBuildExecutor
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GemminiRocketConfig through CHIA/Chipyard")
    parser.add_argument("--output", default="results/real-gemmini-build.jsonl")
    parser.add_argument("--chipyard-path", default="/home/ray/chipyard")
    parser.add_argument("--config", default="GemminiRocketConfig")
    parser.add_argument("--config-package", default="chipyard")
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()

    action = TypedAction(
        kind=ActionKind.BUILD,
        target="gemmini-verilator",
        params={
            "command": "chia:ChiselBuildNode.build",
            "chipyard_path": args.chipyard_path,
            "config": args.config,
            "config_package": args.config_package,
            "target": "verilator",
            "make_jobs": args.jobs,
            "timeout_seconds": args.timeout_seconds,
            "clean": not args.no_clean,
        },
    )

    result = run_action(
        action,
        variant="S2-real-gemmini-build",
        task_id="gate-a-2-gemmini-build",
        safety_enabled=True,
        executor=GemminiChiselBuildExecutor(),
    )
    append_jsonl(args.output, result.record)
    print(json.dumps(result.record, indent=2, sort_keys=True, ensure_ascii=False))

    if result.record["mocked"] is not False:
        raise RuntimeError("Gemmini build was incorrectly marked mocked")
    if result.record["verification"] != "PASS":
        raise SystemExit(1)

    print(f"Gate A.2 PASS: real Gemmini simulator build recorded in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
