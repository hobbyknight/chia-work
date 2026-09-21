#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chia_work.gemini_agent import GeminiTypedActionAgent


def _error_details(exc: Exception) -> dict[str, Any]:
    details: dict[str, Any] = {
        "type": f"{type(exc).__module__}.{type(exc).__name__}",
        "message": str(exc),
    }
    for name in ("code", "status_code"):
        value = getattr(exc, name, None)
        if value is not None:
            details[name] = value
    return details


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Gemini structured TypedAction generation without executing the action"
    )
    parser.add_argument("--config", default="configs/hardware-pilot.json")
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    record: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "probe": "gemini-structured-typed-action-only",
        "model": args.model,
        "task_source": str(config_path),
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT"),
        "location": os.environ.get("GOOGLE_CLOUD_LOCATION"),
        "enterprise": os.environ.get("GOOGLE_GENAI_USE_ENTERPRISE"),
        "executed": False,
    }

    try:
        proposal = GeminiTypedActionAgent(model=args.model).propose(config["task_prompt"])
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = _error_details(exc)
        exit_code = 1
    else:
        record.update(
            {
                "status": "PASS",
                "agent_model": proposal.model,
                "action": proposal.action.to_dict(),
                "usage": proposal.usage,
            }
        )
        exit_code = 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
