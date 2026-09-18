#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chia_work.actions import TypedAction
from chia_work.agentic_loop import run_agentic_task
from chia_work.gemini_agent import GeminiTypedActionAgent
from chia_work.gemmini_mvin_mvout import GemminiMvinMvoutExecutor
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl
from chia_work.variants import get_variant


def posthoc_task_success(record: dict) -> bool:
    """Experiment evaluator oracle; variants U0-S2 do not consume this signal."""
    tool = record.get("tool_result") or {}
    return bool(tool.get("exit_code") == 0 and tool.get("verified") is True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run cached real Gemmini U0-S4 pilot")
    parser.add_argument("--config", default="configs/hardware-pilot.json")
    parser.add_argument("--output", default="results/hardware-pilot.jsonl")
    parser.add_argument("--warmup-output", default="results/hardware-pilot-warmup.jsonl")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    executor = GemminiMvinMvoutExecutor()

    # Setup/warm-up is explicitly excluded from comparative timing. It forces
    # the simulator + workload to exist once so variant runs mostly exercise
    # incremental build checks and the same Verilator workload.
    warmup_action = TypedAction.from_dict(config["warmup_action"])
    warmup = run_action(
        warmup_action,
        variant="WARMUP",
        task_id=f"{config['task_id']}-warmup",
        safety_enabled=True,
        executor=executor,
        verification_enabled=True,
    )
    warmup.record["excluded_from_comparative_metrics"] = True
    append_jsonl(args.warmup_output, warmup.record)
    if warmup.record["verification"] != "PASS" or warmup.record["mocked"] is not False:
        print(json.dumps(warmup.record, indent=2, sort_keys=True, ensure_ascii=False))
        raise SystemExit("Hardware pilot warm-up failed; comparative runs were not started")

    agent = GeminiTypedActionAgent(model=args.model)
    repetitions = int(config.get("repetitions", 1))
    records = []

    for variant in config["variants"]:
        spec = get_variant(variant)
        for repetition in range(repetitions):
            loop = run_agentic_task(
                config["task_prompt"],
                variant=variant,
                task_id=config["task_id"],
                executor=executor,
                agent=agent,
                max_retries=2,
            )
            record = loop.final.record
            record["suite"] = config["suite"]
            record["repetition"] = repetition
            record["warm_cache"] = True
            record["posthoc_task_success"] = posthoc_task_success(record)
            record["variant_spec"] = {
                "safety_enabled": spec.safety_enabled,
                "semantic_policy_enabled": spec.semantic_policy_enabled,
                "verification_enabled": spec.verification_enabled,
                "recovery_enabled": spec.recovery_enabled,
            }
            append_jsonl(output, record)
            records.append(record)
            print(
                f"{variant} rep={repetition}: safety={record['safety_decision']} "
                f"verification={record['verification']} success={record['posthoc_task_success']} "
                f"retries={record['retry_count']}"
            )

    failed = [r for r in records if not r["posthoc_task_success"]]
    print(f"Wrote {len(records)} real pilot records to {output}; post-hoc failures={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
