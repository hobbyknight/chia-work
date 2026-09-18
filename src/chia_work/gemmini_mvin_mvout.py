from __future__ import annotations

import hashlib
from typing import Any

from .actions import ActionKind, TypedAction


class GemminiMvinMvoutExecutor:
    """Run Gemmini's self-checking ``mvin_mvout`` bare-metal accelerator test.

    Pipeline (all real CHIA tasks):
      1. build ``GemminiRocketConfig`` Verilator simulator;
      2. build the upstream Gemmini RoCC bare-metal test binary;
      3. run the ELF through ``VerilatorRunNode``;
      4. accept only simulator exit code 0 (the test exits 1 on matrix mismatch).

    The Gemmini software checkout is expected at the path provisioned by the
    official CHIA Chipyard image. No network fetch is performed inside a run.
    """

    mocked = False

    def execute(self, action: TypedAction) -> dict[str, Any]:
        if action.kind != ActionKind.RUN_BENCHMARK:
            raise ValueError(
                f"GemminiMvinMvoutExecutor only accepts RUN_BENCHMARK, got {action.kind.value}"
            )

        from chia.base.ChiaFunction import ChiaFunction, get
        from chia.chipyard.chisel_build_node import ChiselBuildNode
        from chia.chipyard.state_def import BuildTarget
        from chia.chipyard.verilator_run_node import VerilatorRunNode

        params = action.params
        config = str(params.get("config", "GemminiRocketConfig"))
        make_jobs = int(params.get("make_jobs", 16))
        build_timeout = int(params.get("build_timeout_seconds", 3600))
        workload_timeout = int(params.get("workload_build_timeout_seconds", 1800))
        run_timeout = int(params.get("run_timeout_seconds", 900))
        max_cycles = int(params.get("max_cycles", 20_000_000))
        force_workload_build = bool(params.get("clean", True))
        gemmini_tests_path = str(
            params.get(
                "gemmini_tests_path",
                "/home/ray/chipyard/generators/gemmini/software/gemmini-rocc-tests",
            )
        )

        build_node = ChiselBuildNode(
            chipyard_path="/home/ray/chipyard",
            config=config,
            config_package="chipyard",
            target=BuildTarget.VERILATOR,
            make_jobs=make_jobs,
            timeout_seconds=build_timeout,
            clean=force_workload_build,
            name="safeagent-gemmini-mvin-mvout",
        )

        @ChiaFunction(resources={"chipyard": 1})
        def build_mvin_mvout(
            tests_path: str, timeout_seconds: int, force_build: bool
        ) -> dict[str, Any]:
            import hashlib as _hashlib
            import os
            import subprocess

            binary_path = os.path.join(
                tests_path, "build", "bareMetalC", "mvin_mvout-baremetal"
            )
            source_path = os.path.join(tests_path, "bareMetalC", "mvin_mvout.c")
            build_script = os.path.join(tests_path, "build.sh")

            def _git(*args: str) -> str:
                try:
                    proc = subprocess.run(
                        ["git", *args],
                        cwd=tests_path,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    return proc.stdout.strip() if proc.returncode == 0 else ""
                except Exception:
                    return ""

            git_commit = _git("rev-parse", "HEAD")
            git_status = _git("status", "--porcelain")

            if not os.path.isfile(source_path) or not os.path.isfile(build_script):
                return {
                    "success": False,
                    "returncode": 2,
                    "stdout": "",
                    "stderr": f"Gemmini RoCC tests not provisioned at {tests_path}",
                    "binary": b"",
                    "binary_sha256": "",
                    "source_sha256": "",
                    "git_commit": git_commit,
                    "git_dirty": bool(git_status),
                    "built_this_run": False,
                }

            with open(source_path, "rb") as source_file:
                source_bytes = source_file.read()
            source_sha = _hashlib.sha256(source_bytes).hexdigest()

            stdout = ""
            stderr = ""
            returncode = 0
            built_this_run = False
            if force_build or not os.path.isfile(binary_path):
                built_this_run = True
                try:
                    proc = subprocess.run(
                        ["./build.sh", "bareMetalC"],
                        cwd=tests_path,
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                        check=False,
                    )
                    stdout = proc.stdout
                    stderr = proc.stderr
                    returncode = proc.returncode
                except subprocess.TimeoutExpired as exc:
                    stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
                    stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
                    stderr += f"\n[mvin_mvout build] timeout after {timeout_seconds}s"
                    returncode = -1

            if returncode != 0 or not os.path.isfile(binary_path):
                return {
                    "success": False,
                    "returncode": returncode if returncode != 0 else 3,
                    "stdout": stdout,
                    "stderr": stderr or "mvin_mvout-baremetal not produced",
                    "binary": b"",
                    "binary_sha256": "",
                    "source_sha256": source_sha,
                    "git_commit": git_commit,
                    "git_dirty": bool(git_status),
                    "built_this_run": built_this_run,
                }

            with open(binary_path, "rb") as binary_file:
                binary = binary_file.read()
            return {
                "success": bool(binary),
                "returncode": 0 if binary else 4,
                "stdout": stdout,
                "stderr": stderr,
                "binary": binary,
                "binary_sha256": _hashlib.sha256(binary).hexdigest(),
                "source_sha256": source_sha,
                "git_commit": git_commit,
                "git_dirty": bool(git_status),
                "force_build": force_build,
                "built_this_run": built_this_run,
            }

        simulator_ref = build_node.build.chia_remote(build_node)
        workload_ref = build_mvin_mvout.chia_remote(
            gemmini_tests_path, workload_timeout, force_workload_build
        )
        simulator = get(simulator_ref)
        workload = get(workload_ref)

        if not simulator.success:
            return {
                "backend": "chia-gemmini-mvin-mvout",
                "status": "simulator_build_failed",
                "exit_code": int(simulator.returncode),
                "verified": False,
                "stderr_tail": simulator.stderr[-4000:],
            }
        if not workload.get("success"):
            return {
                "backend": "chia-gemmini-mvin-mvout",
                "status": "workload_build_failed",
                "exit_code": int(workload.get("returncode", 1)),
                "verified": False,
                "stdout_tail": str(workload.get("stdout", ""))[-4000:],
                "stderr_tail": str(workload.get("stderr", ""))[-4000:],
                "source_sha256": workload.get("source_sha256", ""),
                "gemmini_tests_git_commit": workload.get("git_commit", ""),
                "gemmini_tests_git_dirty": workload.get("git_dirty"),
                "workload_built_this_run": workload.get("built_this_run"),
            }

        run_node = VerilatorRunNode()
        run_result = get(
            run_node.run.chia_remote(
                run_node,
                simulator,
                workload["binary"],
                "mvin_mvout-baremetal",
                "/home/ray/verilator-work",
                {},
                max_cycles,
                run_timeout,
                {},
                False,
                False,
            )
        )

        simulator_binary = simulator.simulator_binary_content or b""
        verified = bool(run_result.success and run_result.returncode == 0)
        return {
            "backend": "chia-gemmini-mvin-mvout",
            "status": "success" if run_result.success else "run_failed",
            "exit_code": int(run_result.returncode),
            "verified": verified,
            "oracle": "upstream mvin_mvout exits 1 on matrix mismatch; exit 0 means pass",
            "config": simulator.config,
            "simulator_binary_name": simulator.simulator_binary_name,
            "simulator_binary_size_bytes": len(simulator_binary),
            "simulator_binary_sha256": hashlib.sha256(simulator_binary).hexdigest(),
            "workload_binary_name": "mvin_mvout-baremetal",
            "workload_binary_size_bytes": len(workload["binary"]),
            "workload_binary_sha256": workload["binary_sha256"],
            "workload_source_sha256": workload["source_sha256"],
            "gemmini_tests_git_commit": workload.get("git_commit", ""),
            "gemmini_tests_git_dirty": workload.get("git_dirty"),
            "workload_force_build": workload.get("force_build"),
            "workload_built_this_run": workload.get("built_this_run"),
            "run_log_tail": run_result.log[-4000:],
            "run_out_tail": run_result.out[-4000:],
            "max_cycles": max_cycles,
        }
