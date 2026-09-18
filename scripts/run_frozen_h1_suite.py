#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from chia_work.actions import TypedAction
from chia_work.agentic_loop import run_agentic_task
from chia_work.gemini_agent import GeminiTypedActionAgent
from chia_work.gemmini_mvin_mvout import GemminiMvinMvoutExecutor
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl
from chia_work.variants import get_variant


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _last_jsonl(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"required gate evidence missing: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise SystemExit(f"required gate evidence is empty: {path}")
    return rows[-1]


def require_prior_gates() -> None:
    checks = [
        (Path("results/real-gemmini-build.jsonl"), "A.2-real"),
        (Path("results/real-gemmini-mvin-mvout.jsonl"), "A.2b"),
        (Path("results/real-gemini-gemmini-mvin-mvout.jsonl"), "A.3"),
    ]
    for path, gate in checks:
        row = _last_jsonl(path)
        if row.get("mocked") is not False or row.get("verification") != "PASS":
            raise SystemExit(f"{gate} evidence is not a real PASS: {path}")
    print("Required A.2/A.2b/A.3 evidence: PASS")


def posthoc_h1_success(record: dict[str, Any]) -> bool:
    tool = record.get("tool_result") or {}
    return bool(
        record.get("mocked") is False
        and tool.get("backend") == "chia-gemmini-mvin-mvout"
        and tool.get("exit_code") == 0
        and tool.get("verified") is True
        and tool.get("config") == "GemminiRocketConfig"
        and int(tool.get("simulator_binary_size_bytes") or 0) > 0
        and bool(tool.get("simulator_binary_sha256"))
        and int(tool.get("workload_binary_size_bytes") or 0) > 0
        and bool(tool.get("workload_binary_sha256"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen U0-S4 H1 main experiment")
    parser.add_argument("--manifest", default="configs/manifests/h1-main-v1.json")
    parser.add_argument("--model", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    require_prior_gates()
    manifest_path = Path(args.manifest)
    manifest = _load_json(manifest_path)
    manifest_hash = _sha256(manifest_path)
    output = Path(manifest["output"])
    warmup_output = Path(manifest["warmup_output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    warmup_output.parent.mkdir(parents=True, exist_ok=True)

    existing = [str(path) for path in (output, warmup_output) if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"refusing to overwrite existing frozen-run outputs: {existing}; use --overwrite only for an intentional rerun")
    if args.overwrite:
        for path in (output, warmup_output):
            if path.exists():
                path.unlink()

    executor = GemminiMvinMvoutExecutor()
    warmup = run_action(
        TypedAction.from_dict(manifest["warmup_action"]),
        variant="WARMUP",
        task_id=f"{manifest['task_id']}-warmup",
        safety_enabled=True,
        executor=executor,
        verification_enabled=True,
    )
    warmup.record.update(
        {
            "suite": manifest["suite"],
            "experiment_id": manifest["experiment_id"],
            "manifest_path": str(manifest_path),
            "manifest_sha256": manifest_hash,
            "excluded_from_comparative_metrics": True,
        }
    )
    append_jsonl(warmup_output, warmup.record)
    if not posthoc_h1_success(warmup.record):
        raise SystemExit("frozen H1 warm-up failed objective H1 oracle; main runs were not started")

    agent = GeminiTypedActionAgent(model=args.model)
    records: list[dict[str, Any]] = []
    for repetition, order in enumerate(manifest["variant_schedule"]):
        for position, variant in enumerate(order):
            spec = get_variant(variant)
            loop = run_agentic_task(
                manifest["task_prompt"],
                variant=variant,
                task_id=manifest["task_id"],
                executor=executor,
                agent=agent,
                max_retries=int(manifest["max_retries"]),
            )
            record = loop.final.record
            success = posthoc_h1_success(record)
            tool = record.get("tool_result") or {}
            timing_eligible = bool(success and tool.get("workload_built_this_run") is False)
            record.update(
                {
                    "suite": manifest["suite"],
                    "experiment_id": manifest["experiment_id"],
                    "manifest_path": str(manifest_path),
                    "manifest_sha256": manifest_hash,
                    "planned_run_id": f"{manifest['experiment_id']}-r{repetition}-{position}-{variant}",
                    "repetition": repetition,
                    "schedule_position": position,
                    "warm_cache": True,
                    "posthoc_task_success": success,
                    "timing_eligible": timing_eligible,
                    "timing_exclusion_reason": None if timing_eligible else (
                        "task_failed" if not success else "workload_rebuilt_during_timed_run"
                    ),
                    "variant_spec": {
                        "safety_enabled": spec.safety_enabled,
                        "semantic_policy_enabled": spec.semantic_policy_enabled,
                        "verification_enabled": spec.verification_enabled,
                        "recovery_enabled": spec.recovery_enabled,
                    },
                }
            )
            append_jsonl(output, record)
            records.append(record)
            print(
                f"{record['planned_run_id']}: success={success} "
                f"timing_eligible={timing_eligible} retries={record['retry_count']} "
                f"tool_calls={record['tool_call_count']}"
            )

    print(f"Wrote {len(records)} frozen H1 records to {output}")
    failures = sum(not row["posthoc_task_success"] for row in records)
    timing_excluded = sum(not row["timing_eligible"] for row in records)
    print(f"H1 task failures={failures}; timing-excluded rows={timing_excluded}")
    # Experimental failures are data, not a reason to discard the completed batch.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
