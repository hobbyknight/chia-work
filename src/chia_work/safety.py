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
            try:
                make_jobs = int(action.params.get("make_jobs", 16))
                timeout_seconds = int(action.params.get("timeout_seconds", 3600))
            except (TypeError, ValueError):
                return SafetyDecision(Decision.REPAIR, "make_jobs/timeout_seconds must be integers")
            if not 1 <= make_jobs <= 64:
                return SafetyDecision(Decision.REPAIR, "make_jobs must be in [1, 64]")
            if not 60 <= timeout_seconds <= 7200:
                return SafetyDecision(Decision.REPAIR, "timeout_seconds must be in [60, 7200]")
            return SafetyDecision(Decision.ALLOW, "known Gemmini build matches semantic policy")

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

        # Typed CHIA operations are identifiers, not shell command strings.
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
