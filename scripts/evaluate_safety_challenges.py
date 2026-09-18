#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from chia_work.actions import TypedAction
from chia_work.safety import Decision
from chia_work.structured_log import append_jsonl, utc_now_iso
from chia_work.variants import VARIANTS


def classify(decision: str) -> str:
    if decision == "DENY":
        return "BLOCK"
    if decision == "REPAIR":
        return "REPAIR"
    return "ALLOW"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/safety-challenges.json")
    parser.add_argument("--output", default="results/safety-challenges.jsonl")
    parser.add_argument("--summary", default="results/safety-challenges-summary.json")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for variant_name, spec in VARIANTS.items():
        gate = spec.make_gate()
        for case in config["cases"]:
            action = TypedAction.from_dict(case["action"])
            if not spec.safety_enabled:
                decision = "WOULD_EXECUTE"
                reason = "U0 has no pre-execution safety gate; action is not actually executed in this challenge suite"
            else:
                gate_decision = gate.evaluate(action)
                decision = gate_decision.decision.value
                reason = gate_decision.reason

            observed = classify(decision)
            expected = case["expected"]
            correct = observed == expected
            unsafe_case = expected in {"BLOCK", "REPAIR"}
            valid_case = expected == "ALLOW"

            if unsafe_case:
                counters[variant_name]["unsafe_total"] += 1
                if observed in {"BLOCK", "REPAIR"}:
                    counters[variant_name]["unsafe_prevented"] += 1
            if valid_case:
                counters[variant_name]["valid_total"] += 1
                if observed != "ALLOW":
                    counters[variant_name]["false_rejections"] += 1
            counters[variant_name]["cases"] += 1
            counters[variant_name]["correct"] += int(correct)

            append_jsonl(
                output,
                {
                    "schema_version": 1,
                    "timestamp_utc": utc_now_iso(),
                    "suite": config["suite"],
                    "variant": variant_name,
                    "case_id": case["case_id"],
                    "action": action.to_dict(),
                    "expected": expected,
                    "decision": decision,
                    "observed": observed,
                    "reason": reason,
                    "correct": correct,
                    "counterfactual_only": True,
                    "executed": False,
                    "mocked": False,
                },
            )

    summary: dict[str, object] = {
        "suite": config["suite"],
        "counterfactual_only": True,
        "executed": False,
        "variants": {},
    }
    for variant_name in VARIANTS:
        c = counters[variant_name]
        unsafe_total = c["unsafe_total"]
        valid_total = c["valid_total"]
        summary["variants"][variant_name] = {
            "cases": c["cases"],
            "policy_accuracy": c["correct"] / c["cases"] if c["cases"] else None,
            "unsafe_action_prevention_rate": (
                c["unsafe_prevented"] / unsafe_total if unsafe_total else None
            ),
            "false_rejection_rate": (
                c["false_rejections"] / valid_total if valid_total else None
            ),
            "unsafe_prevented": c["unsafe_prevented"],
            "unsafe_total": unsafe_total,
            "false_rejections": c["false_rejections"],
            "valid_total": valid_total,
        }

    Path(args.summary).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote non-executing challenge records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
