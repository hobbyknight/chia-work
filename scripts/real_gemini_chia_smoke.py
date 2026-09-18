#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from chia_work.chia_adapter import ChiaLocalExecutor
from chia_work.gemini_agent import GeminiTypedActionAgent
from chia_work.runner import run_action
from chia_work.structured_log import append_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gemini -> TypedAction -> SafetyGate -> real CHIA")
    parser.add_argument("--output", default="results/real-gemini-chia-smoke.jsonl")
    parser.add_argument("--model", default=None)
    parser.add_argument("--ray-address", default=None)
    args = parser.parse_args()

    task = (
        "For this integration smoke test, propose one RUN_BENCHMARK action targeting "
        "chia-local-smoke. Set params.command to 'chia:identity' and include a short "
        "non-secret payload identifying the Gate A agent smoke test."
    )
    proposal = GeminiTypedActionAgent(model=args.model).propose(task)

    result = run_action(
        proposal.action,
        variant="S2-real-gemini-chia-smoke",
        task_id="gate-a-3-gemini-chia",
        safety_enabled=True,
        executor=ChiaLocalExecutor(ray_address=args.ray_address),
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
        raise SystemExit("Gemini proposal did not pass SafetyGate")
    if record["mocked"] is not False or record["verification"] != "PASS":
        raise SystemExit("Real Gemini -> CHIA smoke failed verification")

    print(f"Gate A.3 PASS: Gemini -> SafetyGate -> CHIA record written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
