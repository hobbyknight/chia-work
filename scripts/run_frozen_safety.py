#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen non-executing safety manifest")
    parser.add_argument("--manifest", default="configs/manifests/safety-v1.json")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if manifest.get("counterfactual_only") is not True or manifest.get("executed") is not False:
        raise SystemExit("refusing to run safety manifest that is not explicitly counterfactual/non-executing")
    subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_safety_challenges.py",
            "--config",
            manifest["cases_file"],
            "--output",
            manifest["output"],
            "--summary",
            manifest["summary"],
        ],
        check=True,
    )
    summary = json.loads(Path(manifest["summary"]).read_text(encoding="utf-8"))
    for variant in manifest["variants"]:
        row = summary["variants"][variant]
        if row["unsafe_total"] != len(manifest["unsafe_case_ids"]):
            raise SystemExit(f"unsafe denominator drift for {variant}: {row}")
        if row["valid_total"] != len(manifest["valid_case_ids"]):
            raise SystemExit(f"valid denominator drift for {variant}: {row}")
    print("Frozen safety manifest: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
