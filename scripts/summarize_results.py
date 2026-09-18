#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--allow-mocked", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise SystemExit("no records")

    mocked_count = sum(bool(row.get("mocked")) for row in records)
    if mocked_count and not args.allow_mocked:
        raise SystemExit(
            f"refusing to summarize {mocked_count} mocked records; pass --allow-mocked only for plumbing checks"
        )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        grouped[str(row.get("variant", "UNKNOWN"))].append(row)

    print("variant,runs,allowed_or_executed,denied,repair,verified_pass,mean_wall_s")
    for variant in sorted(grouped):
        rows = grouped[variant]
        denied = sum(row.get("safety_decision") == "DENY" for row in rows)
        repair = sum(row.get("safety_decision") == "REPAIR" for row in rows)
        executed = sum(row.get("tool_result") is not None for row in rows)
        verified = sum(row.get("verification") == "PASS" for row in rows)
        mean_wall = sum(float(row.get("wall_time_seconds", 0.0)) for row in rows) / len(rows)
        print(f"{variant},{len(rows)},{executed},{denied},{repair},{verified},{mean_wall:.6f}")

    if mocked_count:
        print("WARNING: summary includes MOCKED records and is not paper evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
