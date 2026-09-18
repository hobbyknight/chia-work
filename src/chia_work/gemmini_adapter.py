from __future__ import annotations

import hashlib
import os
from typing import Any

from .actions import ActionKind, TypedAction


class GemminiChiselBuildExecutor:
    """Build a Gemmini Chipyard configuration through CHIA's ChiselBuildNode.

    This is a real hardware-tool path. It expects the current Ray/CHIA cluster
    to expose a worker resource named ``chipyard`` as required by upstream
    ``ChiselBuildNode.build``.
    """

    mocked = False

    def execute(self, action: TypedAction) -> dict[str, Any]:
        if action.kind != ActionKind.BUILD:
            raise ValueError(f"GemminiChiselBuildExecutor only accepts BUILD, got {action.kind.value}")

        from chia.base.ChiaFunction import get
        from chia.chipyard.chisel_build_node import ChiselBuildNode
        from chia.chipyard.state_def import BuildTarget

        params = action.params
        chipyard_path = str(params.get("chipyard_path") or os.environ.get("CHIPYARD_PATH", "/home/ray/chipyard"))
        config = str(params.get("config", "GemminiRocketConfig"))
        config_package = str(params.get("config_package", "chipyard"))
        target_name = str(params.get("target", "verilator"))
        try:
            target = BuildTarget(target_name)
        except ValueError as exc:
            raise ValueError(f"unsupported BuildTarget {target_name!r}") from exc

        node = ChiselBuildNode(
            chipyard_path=chipyard_path,
            config=config,
            config_package=config_package,
            target=target,
            make_jobs=int(params.get("make_jobs", 16)),
            timeout_seconds=int(params.get("timeout_seconds", 3600)),
            clean=bool(params.get("clean", True)),
            clean_sim=bool(params.get("clean_sim", False)),
            collect_generated_src=bool(params.get("collect_generated_src", False)),
            name="safeagent-gemmini",
        )

        artifact = get(node.build.chia_remote(node))
        binary = artifact.simulator_binary_content or b""
        binary_sha256 = hashlib.sha256(binary).hexdigest() if binary else ""
        verified = bool(artifact.success and artifact.returncode == 0 and binary)

        return {
            "backend": "chia-chipyard-chisel-build",
            "status": "success" if artifact.success else "failed",
            "exit_code": int(artifact.returncode),
            "verified": verified,
            "config": artifact.config,
            "config_package": artifact.config_package,
            "target": artifact.target.value,
            "simulator_binary_name": artifact.simulator_binary_name,
            "simulator_binary_size_bytes": len(binary),
            "simulator_binary_sha256": binary_sha256,
            "stdout_tail": artifact.stdout[-4000:],
            "stderr_tail": artifact.stderr[-4000:],
            "generated_src_file_count": len(artifact.generated_src_files),
        }
