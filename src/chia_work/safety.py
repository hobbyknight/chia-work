from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .actions import ActionKind, TypedAction


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REPAIR = "REPAIR"


@dataclass(frozen=True)
class SafetyDecision:
    decision: Decision
    reason: str


class SafetyGate:
    """Small, auditable experimental policy gate for the hackathon.

    The gate combines generic command checks with semantic policies for known
    typed targets. It is an experiment component, not a production sandbox.
    """

    DEFAULT_ALLOWED = {
        ActionKind.BUILD,
        ActionKind.SIMULATE,
        ActionKind.MODIFY_CONFIG,
        ActionKind.RUN_BENCHMARK,
    }

    BLOCKED_COMMAND_FRAGMENTS = (
        "rm -rf /",
        "sudo ",
        "curl | sh",
        "curl|sh",
        "wget | sh",
        "wget|sh",
        ":(){:|:&};:",
    )

    SHELL_META_FRAGMENTS = ("&&", "||", ";", "`", "$(", ">", "<")

    def __init__(self, allowed_kinds: set[ActionKind] | None = None) -> None:
        self.allowed_kinds = allowed_kinds or set(self.DEFAULT_ALLOWED)

    @staticmethod
    def _int_param(action: TypedAction, name: str, default: int) -> int | None:
        try:
            return int(action.params.get(name, default))
        except (TypeError, ValueError):
            return None

    def _validate_resource_budget(
        self,
        action: TypedAction,
        *,
        max_cycles_default: int,
        max_cycles_upper: int,
        include_workload_build: bool = False,
    ) -> SafetyDecision | None:
        make_jobs = self._int_param(action, "make_jobs", 16)
        build_timeout = self._int_param(action, "build_timeout_seconds", 3600)
        run_timeout = self._int_param(action, "run_timeout_seconds", 600)
        max_cycles = self._int_param(action, "max_cycles", max_cycles_default)
        workload_timeout = (
            self._int_param(action, "workload_build_timeout_seconds", 1800)
            if include_workload_build
            else 1800
        )
        if None in (make_jobs, build_timeout, run_timeout, max_cycles, workload_timeout):
            return SafetyDecision(Decision.REPAIR, "resource-budget parameters must be integers")
        if not 1 <= make_jobs <= 64:
            return SafetyDecision(Decision.REPAIR, "make_jobs must be in [1, 64]")
        if not 60 <= build_timeout <= 7200:
            return SafetyDecision(Decision.REPAIR, "build_timeout_seconds must be in [60, 7200]")
        if not 30 <= run_timeout <= 1800:
            return SafetyDecision(Decision.REPAIR, "run_timeout_seconds must be in [30, 1800]")
        if include_workload_build and not 60 <= workload_timeout <= 3600:
            return SafetyDecision(
                Decision.REPAIR, "workload_build_timeout_seconds must be in [60, 3600]"
            )
        if not 10_000 <= max_cycles <= max_cycles_upper:
            return SafetyDecision(Decision.REPAIR, "max_cycles outside approved range")
        return None

    def _known_target_policy(self, action: TypedAction) -> SafetyDecision | None:
        if action.target == "chia-local-smoke":
            if action.kind != ActionKind.RUN_BENCHMARK:
                return SafetyDecision(Decision.REPAIR, "chia-local-smoke requires RUN_BENCHMARK")
            if action.params.get("command") != "chia:identity":
                return SafetyDecision(Decision.DENY, "chia-local-smoke only permits chia:identity")
            payload = str(action.params.get("payload", ""))
            if len(payload) > 256:
                return SafetyDecision(Decision.REPAIR, "smoke payload exceeds 256 characters")
            return SafetyDecision(Decision.ALLOW, "known CHIA smoke action matches policy")

        if action.target == "gemmini-verilator":
            if action.kind != ActionKind.BUILD:
                return SafetyDecision(Decision.REPAIR, "gemmini-verilator requires BUILD")
            if action.params.get("command") != "chia:ChiselBuildNode.build":
                return SafetyDecision(
                    Decision.DENY,
                    "gemmini-verilator only permits the typed ChiselBuildNode build operation",
                )
            if action.params.get("config", "GemminiRocketConfig") != "GemminiRocketConfig":
                return SafetyDecision(Decision.DENY, "unapproved Gemmini Chipyard config")
            if action.params.get("config_package", "chipyard") != "chipyard":
                return SafetyDecision(Decision.DENY, "unapproved Chipyard config package")
            if action.params.get("target", "verilator") != "verilator":
                return SafetyDecision(Decision.DENY, "only the non-debug Verilator target is approved")
            chipyard_path = action.params.get("chipyard_path")
            if chipyard_path not in (None, "/home/ray/chipyard"):
                return SafetyDecision(Decision.DENY, "unapproved Chipyard path")
            make_jobs = self._int_param(action, "make_jobs", 16)
            timeout_seconds = self._int_param(action, "timeout_seconds", 3600)
            if make_jobs is None or timeout_seconds is None:
                return SafetyDecision(Decision.REPAIR, "make_jobs/timeout_seconds must be integers")
            if not 1 <= make_jobs <= 64:
                return SafetyDecision(Decision.REPAIR, "make_jobs must be in [1, 64]")
            if not 60 <= timeout_seconds <= 7200:
                return SafetyDecision(Decision.REPAIR, "timeout_seconds must be in [60, 7200]")
            return SafetyDecision(Decision.ALLOW, "known Gemmini build matches semantic policy")

        if action.target == "gemmini-sanity-run":
            if action.kind != ActionKind.RUN_BENCHMARK:
                return SafetyDecision(Decision.REPAIR, "gemmini-sanity-run requires RUN_BENCHMARK")
            if action.params.get("command") != "chia:GemminiSanity.run":
                return SafetyDecision(
                    Decision.DENY,
                    "gemmini-sanity-run only permits the typed sanity pipeline",
                )
            if action.params.get("config", "GemminiRocketConfig") != "GemminiRocketConfig":
                return SafetyDecision(Decision.DENY, "unapproved Gemmini sanity config")
            budget = self._validate_resource_budget(
                action, max_cycles_default=2_000_000, max_cycles_upper=20_000_000
            )
            if budget is not None:
                return budget
            return SafetyDecision(Decision.ALLOW, "known Gemmini sanity run matches semantic policy")

        if action.target == "gemmini-mvin-mvout":
            if action.kind != ActionKind.RUN_BENCHMARK:
                return SafetyDecision(Decision.REPAIR, "gemmini-mvin-mvout requires RUN_BENCHMARK")
            if action.params.get("command") != "chia:GemminiMvinMvout.run":
                return SafetyDecision(
                    Decision.DENY,
                    "gemmini-mvin-mvout only permits the typed accelerator workload",
                )
            if action.params.get("config", "GemminiRocketConfig") != "GemminiRocketConfig":
                return SafetyDecision(Decision.DENY, "unapproved Gemmini accelerator config")
            tests_path = action.params.get("gemmini_tests_path")
            approved_path = "/home/ray/chipyard/generators/gemmini/software/gemmini-rocc-tests"
            if tests_path not in (None, approved_path):
                return SafetyDecision(Decision.DENY, "unapproved Gemmini test checkout path")
            budget = self._validate_resource_budget(
                action,
                max_cycles_default=20_000_000,
                max_cycles_upper=100_000_000,
                include_workload_build=True,
            )
            if budget is not None:
                return budget
            return SafetyDecision(
                Decision.ALLOW, "known Gemmini mvin/mvout workload matches semantic policy"
            )

        return None

    def evaluate(self, action: TypedAction) -> SafetyDecision:
        if not action.target.strip():
            return SafetyDecision(Decision.REPAIR, "missing target")

        if action.kind not in self.allowed_kinds:
            return SafetyDecision(
                Decision.DENY,
                f"action kind {action.kind.value} is not enabled by policy",
            )

        command = str(action.params.get("command", ""))
        command_lower = command.lower()
        for fragment in self.BLOCKED_COMMAND_FRAGMENTS:
            if fragment in command_lower:
                return SafetyDecision(
                    Decision.DENY,
                    f"command contains blocked fragment: {fragment}",
                )

        if not command.startswith("chia:"):
            for fragment in self.SHELL_META_FRAGMENTS:
                if fragment in command:
                    return SafetyDecision(
                        Decision.DENY,
                        f"command contains shell metacharacter fragment: {fragment}",
                    )

        if action.kind in {ActionKind.BUILD, ActionKind.SIMULATE, ActionKind.RUN_BENCHMARK}:
            if not command.strip():
                return SafetyDecision(Decision.REPAIR, "missing command for executable action")

        known = self._known_target_policy(action)
        if known is not None:
            return known

        return SafetyDecision(Decision.ALLOW, "generic policy checks passed")
