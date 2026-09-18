#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from chia_work.gemini_agent import GeminiTypedActionAgent
from chia_work.gemmini_mvin_mvout import GemminiMvinMvoutExecutor
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Gemini -> SafetyGate -> CHIA -> Gemmini mvin/mvout workload"
    )
    parser.add_argument("--output", default="results/real-gemini-gemmini-mvin-mvout.jsonl")
    parser.add_argument("--model", default=None)
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--build-timeout-seconds", type=int, default=3600)
    parser.add_argument("--workload-build-timeout-seconds", type=int, default=1800)
    parser.add_argument("--run-timeout-seconds", type=int, default=900)
    parser.add_argument("--max-cycles", type=int, default=20_000_000)
    args = parser.parse_args()

    task = (
        "Propose exactly one RUN_BENCHMARK action for the approved Gemmini mvin/mvout "
        "accelerator workload. The target must be 'gemmini-mvin-mvout'. Set "
        "params.command to 'chia:GemminiMvinMvout.run', params.config to "
        "'GemminiRocketConfig', "
        f"params.make_jobs to {args.jobs}, "
        f"params.build_timeout_seconds to {args.build_timeout_seconds}, "
        f"params.workload_build_timeout_seconds to {args.workload_build_timeout_seconds}, "
        f"params.run_timeout_seconds to {args.run_timeout_seconds}, "
        f"params.max_cycles to {args.max_cycles}, and params.clean to true. "
        "Do not propose any shell action, path override, or alternative configuration."
    )
    proposal = GeminiTypedActionAgent(model=args.model).propose(task)

    result = run_action(
        proposal.action,
        variant="S4-real-gemini-gemmini-mvin-mvout",
        task_id="accelerator-mvin-mvout-agentic",
        safety_enabled=True,
        executor=GemminiMvinMvoutExecutor(),
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
        raise SystemExit("Gemini mvin/mvout proposal did not pass SafetyGate")
    if record["mocked"] is not False or record["verification"] != "PASS":
        raise SystemExit("Gemini -> Gemmini mvin/mvout workload failed verification")

    print(f"Agentic accelerator workload PASS: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
