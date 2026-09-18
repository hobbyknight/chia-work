#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from chia_work.actions import ActionKind, TypedAction
from chia_work.gemmini_adapter import GemminiChiselBuildExecutor
from chia_work.safety import Decision, SafetyGate


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build_gate_a2_action(*, jobs: int = 16, timeout_seconds: int = 3600) -> TypedAction:
    return TypedAction(
        kind=ActionKind.BUILD,
        target="gemmini-verilator",
        params={
            "command": "chia:ChiselBuildNode.build",
            "chipyard_path": "/home/ray/chipyard",
            "config": "GemminiRocketConfig",
            "config_package": "chipyard",
            "target": "verilator",
            "make_jobs": jobs,
            "timeout_seconds": timeout_seconds,
            "clean": True,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Gate A.2 CHIA -> Chipyard -> Gemmini build contract without running the expensive build"
    )
    parser.add_argument("--cluster", default="configs/chia-gemmini-local.yaml")
    parser.add_argument("--output", default="results/gate-a2-preflight.json")
    args = parser.parse_args()

    # Safe deterministic placeholders let CHIA expand and validate the cluster
    # contract in CI without provisioning any workers.
    os.environ.setdefault("THIS_MACHINE", "127.0.0.1")
    os.environ.setdefault("USER", "chia-ci")
    os.environ.setdefault("CHIA_WORK_DIR", str(Path.cwd()))

    from chia.cluster.config import build_config, load_raw_config
    from chia.chipyard.chisel_build_node import ChiselBuildNode
    from chia.chipyard.state_def import BuildTarget
    import ray

    raw = load_raw_config(args.cluster)
    cluster = build_config(raw)

    _require("gemmini_chipyard" in cluster.node_types, "missing gemmini_chipyard node type")
    chipyard_worker = cluster.node_types["gemmini_chipyard"]
    _require(chipyard_worker.resources.get("chipyard") == 1, "chipyard worker must expose chipyard=1")
    _require(chipyard_worker.num_workers == 1, "Gate A.2 expects exactly one Chipyard worker")
    _require(chipyard_worker.docker is not None, "Chipyard worker must use a Docker image")
    _require(
        chipyard_worker.docker.image == "ghcr.io/ucb-bar/chia-chisel-build:latest",
        f"unexpected Chipyard image: {chipyard_worker.docker.image}",
    )
    _require(
        "source /home/ray/chipyard/env.sh" in chipyard_worker.worker_setup_commands,
        "Chipyard worker must source /home/ray/chipyard/env.sh",
    )

    # A.2a only needs the chipyard worker, but validate the next-stage resources
    # now so A.2b does not discover topology mistakes later.
    _require("gemmini_verilator" in cluster.node_types, "missing gemmini_verilator node type")
    _require(
        cluster.node_types["gemmini_verilator"].resources.get("verilator_run") == 1,
        "Verilator worker must expose verilator_run=1",
    )
    _require("riscv_build" in cluster.node_types, "missing riscv_build node type")
    _require(
        cluster.node_types["riscv_build"].resources.get("riscv_build") == 1,
        "RISC-V worker must expose riscv_build=1",
    )

    action = build_gate_a2_action()
    decision = SafetyGate().evaluate(action)
    _require(decision.decision == Decision.ALLOW, f"SafetyGate rejected Gate A.2 action: {decision}")
    _require(GemminiChiselBuildExecutor.mocked is False, "Gemmini executor must never be marked mocked")

    # Instantiate the exact upstream node used by the executor, but do not
    # dispatch it. This catches API/constructor drift while keeping CI cheap.
    node = ChiselBuildNode(
        chipyard_path="/home/ray/chipyard",
        config="GemminiRocketConfig",
        config_package="chipyard",
        target=BuildTarget.VERILATOR,
        make_jobs=16,
        timeout_seconds=3600,
        clean=True,
        name="safeagent-gemmini-preflight",
    )
    build_options: dict[str, Any] = dict(getattr(node.build, "_chia_options", {}))
    resources = dict(build_options.get("resources", {}))
    _require(resources.get("chipyard") == 1, f"upstream ChiselBuildNode no longer requests chipyard=1: {resources}")

    summary = {
        "gate": "A.2-preflight",
        "status": "PASS",
        "mocked": False,
        "executes_hardware_build": False,
        "cluster_file": args.cluster,
        "head_ip": cluster.head_ip,
        "chipyard_resource": chipyard_worker.resources,
        "chipyard_image": chipyard_worker.docker.image,
        "verilator_resource": cluster.node_types["gemmini_verilator"].resources,
        "riscv_build_resource": cluster.node_types["riscv_build"].resources,
        "safety_decision": decision.decision.value,
        "action": action.to_dict(),
        "upstream_build_target": node.target.value,
        "upstream_build_resources": resources,
        "ray_version": ray.__version__,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Gate A.2 preflight PASS: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
