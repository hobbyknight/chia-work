#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from chia_work.gemini_agent import GeminiTypedActionAgent
from chia_work.gemmini_adapter import GemminiChiselBuildExecutor
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Gemini -> TypedAction -> SafetyGate -> CHIA -> Gemmini build"
    )
    parser.add_argument("--output", default="results/real-gemini-gemmini-build.jsonl")
    parser.add_argument("--model", default=None)
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    args = parser.parse_args()

    task = (
        "Propose exactly one BUILD action for the Gemmini Verilator integration test. "
        "The target must be 'gemmini-verilator'. Set params.command to "
        "'chia:ChiselBuildNode.build', params.config to 'GemminiRocketConfig', "
        "params.config_package to 'chipyard', params.target to 'verilator', "
        f"params.make_jobs to {args.jobs}, params.timeout_seconds to {args.timeout_seconds}, "
        "and params.clean to true. Do not propose a shell action."
    )
    proposal = GeminiTypedActionAgent(model=args.model).propose(task)

    result = run_action(
        proposal.action,
        variant="S2-real-gemini-gemmini-build",
        task_id="gate-a-4-gemini-gemmini-build",
        safety_enabled=True,
        executor=GemminiChiselBuildExecutor(),
    )
    record = result.record
    record["agent"] = {
        "provider": "gemini",
        "model": proposal.model,
        "rationale": proposal.rationale,
        "usage": proposal.usage,
        "raw_structured_response": proposal.raw_text,
    }
    append_jsonl(args.output, record)
    print(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False))

    if record["safety_decision"] != "ALLOW":
        raise SystemExit("Gemini Gemmini proposal did not pass SafetyGate")
    if record["mocked"] is not False or record["verification"] != "PASS":
        raise SystemExit("Gemini -> Gemmini build failed verification")

    print(f"Gate A.4 PASS: agentic Gemmini build record written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
