from __future__ import annotations

import hashlib
from typing import Any

from .actions import ActionKind, TypedAction


SANITY_MARKER = "SAFEAGENT_GEMMINI_SANITY_PASS"
SANITY_SOURCE = f'''#include <stdio.h>\n\nint main(void) {{\n    printf("{SANITY_MARKER}\\n");\n    return 0;\n}}\n'''


class GemminiSanityRunExecutor:
    """Real CHIA pipeline: build Gemmini SoC + build ELF + run Verilator."""

    mocked = False

    def execute(self, action: TypedAction) -> dict[str, Any]:
        if action.kind != ActionKind.RUN_BENCHMARK:
            raise ValueError(
                f"GemminiSanityRunExecutor only accepts RUN_BENCHMARK, got {action.kind.value}"
            )

        from chia.base.ChiaFunction import get
        from chia.chipyard.chisel_build_node import ChiselBuildNode
        from chia.chipyard.riscv_build_node import RiscvBuildNode
        from chia.chipyard.state_def import BuildTarget
        from chia.chipyard.verilator_run_node import VerilatorRunNode

        params = action.params
        config = str(params.get("config", "GemminiRocketConfig"))
        make_jobs = int(params.get("make_jobs", 16))
        build_timeout = int(params.get("build_timeout_seconds", 3600))
        run_timeout = int(params.get("run_timeout_seconds", 600))
        max_cycles = int(params.get("max_cycles", 2_000_000))

        build_node = ChiselBuildNode(
            chipyard_path="/home/ray/chipyard",
            config=config,
            config_package="chipyard",
            target=BuildTarget.VERILATOR,
            make_jobs=make_jobs,
            timeout_seconds=build_timeout,
            clean=bool(params.get("clean", True)),
            name="safeagent-gemmini-sanity",
        )
        riscv_node = RiscvBuildNode(timeout_seconds=300)

        # These two independent stages can execute concurrently on distinct
        # CHIA resources (chipyard and riscv_build).
        build_ref = build_node.build.chia_remote(build_node)
        program_ref = riscv_node.build.chia_remote(
            riscv_node,
            SANITY_SOURCE.encode("utf-8"),
            "safeagent_gemmini_sanity",
            "/home/ray/riscv-build-work",
            "verilator",
            "",
            "",
            False,
            True,
            "c",
        )

        build_artifact = get(build_ref)
        program_artifact = get(program_ref)

        if not build_artifact.success:
            return {
                "backend": "chia-gemmini-sanity",
                "status": "build_failed",
                "exit_code": int(build_artifact.returncode),
                "verified": False,
                "build_stderr_tail": build_artifact.stderr[-4000:],
            }
        if not program_artifact.success:
            return {
                "backend": "chia-gemmini-sanity",
                "status": "program_build_failed",
                "exit_code": int(program_artifact.returncode),
                "verified": False,
                "program_stderr_tail": program_artifact.stderr[-4000:],
            }

        run_node = VerilatorRunNode()
        run_result = get(
            run_node.run.chia_remote(
                run_node,
                build_artifact,
                program_artifact.binary_content,
                program_artifact.binary_name,
                "/home/ray/verilator-work",
                {},
                max_cycles,
                run_timeout,
                {},
                False,
                False,
            )
        )

        sim_binary = build_artifact.simulator_binary_content or b""
        program_binary = program_artifact.binary_content or b""
        marker_seen = SANITY_MARKER in run_result.log
        verified = bool(run_result.success and marker_seen)

        return {
            "backend": "chia-gemmini-sanity",
            "status": "success" if run_result.success else "run_failed",
            "exit_code": int(run_result.returncode),
            "verified": verified,
            "marker": SANITY_MARKER,
            "marker_seen": marker_seen,
            "config": build_artifact.config,
            "simulator_binary_name": build_artifact.simulator_binary_name,
            "simulator_binary_size_bytes": len(sim_binary),
            "simulator_binary_sha256": hashlib.sha256(sim_binary).hexdigest(),
            "program_binary_name": program_artifact.binary_name,
            "program_binary_size_bytes": len(program_binary),
            "program_binary_sha256": hashlib.sha256(program_binary).hexdigest(),
            "run_log_tail": run_result.log[-4000:],
            "run_out_tail": run_result.out[-4000:],
            "max_cycles": max_cycles,
        }
