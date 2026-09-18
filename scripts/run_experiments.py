#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chia_work.actions import TypedAction
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default="results/dry_run.jsonl")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if config.get("mocked") is not True:
        raise SystemExit("This scaffold runner only supports mocked=true. Real runs require the CHIA adapter.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    count = 0
    for variant in config["variants"]:
        safety_enabled = variant != "U0"
        for task in config["tasks"]:
            action = TypedAction.from_dict(task)
            result = run_action(
                action,
                variant=variant,
                task_id=task["task_id"],
                safety_enabled=safety_enabled,
            )
            append_jsonl(output, result.record)
            count += 1

    print(f"wrote {count} MOCKED records to {output}")
    print("Do not use this file as hackathon result evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
