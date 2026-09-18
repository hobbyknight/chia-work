#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

from chia_work.chia_adapter import UPSTREAM_CHIA_COMMIT
from chia_work.structured_log import utc_now_iso


IMAGES = [
    "ghcr.io/ucb-bar/chia-chisel-build:latest",
    "ghcr.io/ucb-bar/chia-riscv-cross:latest",
    "ghcr.io/ucb-bar/chia-verilator-run:latest",
]


def command(argv: list[str], cwd: str | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=30)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def git_state(path: str) -> dict[str, Any]:
    rev = command(["git", "rev-parse", "HEAD"], cwd=path)
    status = command(["git", "status", "--porcelain"], cwd=path)
    return {
        "path": path,
        "commit": rev.get("stdout", "") if rev.get("ok") else None,
        "dirty": bool(status.get("stdout")) if status.get("ok") else None,
        "error": None if rev.get("ok") else rev,
    }


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def docker_image(image: str) -> dict[str, Any]:
    inspect = command(
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            "{{json .}}",
        ]
    )
    if not inspect.get("ok"):
        return {"image": image, "available": False, "inspect_error": inspect}
    try:
        data = json.loads(inspect["stdout"])
    except json.JSONDecodeError:
        return {"image": image, "available": True, "raw": inspect["stdout"]}
    return {
        "image": image,
        "available": True,
        "id": data.get("Id"),
        "repo_digests": data.get("RepoDigests", []),
        "created": data.get("Created"),
        "architecture": data.get("Architecture"),
        "os": data.get("Os"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/environment.json")
    args = parser.parse_args()

    record = {
        "schema_version": 1,
        "captured_at_utc": utc_now_iso(),
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "packages": {
            name: package_version(name)
            for name in [
                "chia-work-safeagent",
                "chialoops",
                "ray",
                "google-genai",
                "pydantic",
            ]
        },
        "source": {
            "chia_work": git_state("."),
            "external_chia": git_state("external/chia") if Path("external/chia/.git").exists() else None,
            "expected_upstream_chia_commit": UPSTREAM_CHIA_COMMIT,
        },
        "docker_images": [docker_image(image) for image in IMAGES],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    print(f"Environment provenance written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
