#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from chia_work.gemini_agent import GeminiTypedActionAgent
from chia_work.gemmini_sanity import GemminiSanityRunExecutor
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Gemini -> SafetyGate -> CHIA -> Gemmini build/compile/run"
    )
    parser.add_argument("--output", default="results/real-gemini-gemmini-sanity.jsonl")
    parser.add_argument("--model", default=None)
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--build-timeout-seconds", type=int, default=3600)
    parser.add_argument("--run-timeout-seconds", type=int, default=600)
    parser.add_argument("--max-cycles", type=int, default=2_000_000)
    args = parser.parse_args()

    task = (
        "Propose exactly one RUN_BENCHMARK action for the approved Gemmini sanity pipeline. "
        "The target must be 'gemmini-sanity-run'. Set params.command to "
        "'chia:GemminiSanity.run', params.config to 'GemminiRocketConfig', "
        f"params.make_jobs to {args.jobs}, "
        f"params.build_timeout_seconds to {args.build_timeout_seconds}, "
        f"params.run_timeout_seconds to {args.run_timeout_seconds}, "
        f"params.max_cycles to {args.max_cycles}, and params.clean to true. "
        "Do not propose shell commands."
    )
    proposal = GeminiTypedActionAgent(model=args.model).propose(task)

    result = run_action(
        proposal.action,
        variant="S4-real-gemini-gemmini-sanity",
        task_id="gate-a-6-full-agentic-hardware-path",
        safety_enabled=True,
        executor=GemminiSanityRunExecutor(),
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
        raise SystemExit("Gemini Gemmini sanity proposal did not pass SafetyGate")
    if record["mocked"] is not False or record["verification"] != "PASS":
        raise SystemExit("Full Gemini -> Gemmini sanity path failed verification")

    print(f"Gate A.6 PASS: full agentic hardware record written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
