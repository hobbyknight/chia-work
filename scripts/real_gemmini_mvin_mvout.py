#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from chia_work.actions import ActionKind, TypedAction
from chia_work.gemmini_mvin_mvout import GemminiMvinMvoutExecutor
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Gemmini mvin/mvout workload through CHIA")
    parser.add_argument("--output", default="results/real-gemmini-mvin-mvout.jsonl")
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--build-timeout-seconds", type=int, default=3600)
    parser.add_argument("--workload-build-timeout-seconds", type=int, default=1800)
    parser.add_argument("--run-timeout-seconds", type=int, default=900)
    parser.add_argument("--max-cycles", type=int, default=20_000_000)
    args = parser.parse_args()

    action = TypedAction(
        kind=ActionKind.RUN_BENCHMARK,
        target="gemmini-mvin-mvout",
        params={
            "command": "chia:GemminiMvinMvout.run",
            "config": "GemminiRocketConfig",
            "make_jobs": args.jobs,
            "build_timeout_seconds": args.build_timeout_seconds,
            "workload_build_timeout_seconds": args.workload_build_timeout_seconds,
            "run_timeout_seconds": args.run_timeout_seconds,
            "max_cycles": args.max_cycles,
            "clean": True,
        },
    )
    result = run_action(
        action,
        variant="S3-real-gemmini-mvin-mvout",
        task_id="accelerator-mvin-mvout",
        safety_enabled=True,
        executor=GemminiMvinMvoutExecutor(),
    )
    append_jsonl(args.output, result.record)
    print(json.dumps(result.record, indent=2, sort_keys=True, ensure_ascii=False))

    if result.record["safety_decision"] != "ALLOW":
        raise SystemExit("mvin/mvout action did not pass SafetyGate")
    if result.record["mocked"] is not False or result.record["verification"] != "PASS":
        raise SystemExit("Gemmini mvin/mvout workload failed verification")

    print(f"Accelerator workload PASS: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
