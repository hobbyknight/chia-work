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
    """Experimental policy gate for the hackathon evaluation.

    This is deliberately small and auditable. It is not a production sandbox
    or a complete security boundary.
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

    def __init__(self, allowed_kinds: set[ActionKind] | None = None) -> None:
        self.allowed_kinds = allowed_kinds or set(self.DEFAULT_ALLOWED)

    def evaluate(self, action: TypedAction) -> SafetyDecision:
        if not action.target.strip():
            return SafetyDecision(Decision.REPAIR, "missing target")

        if action.kind not in self.allowed_kinds:
            return SafetyDecision(
                Decision.DENY,
                f"action kind {action.kind.value} is not enabled by policy",
            )

        command = str(action.params.get("command", "")).lower()
        for fragment in self.BLOCKED_COMMAND_FRAGMENTS:
            if fragment in command:
                return SafetyDecision(
                    Decision.DENY,
                    f"command contains blocked fragment: {fragment}",
                )

        if action.kind in {ActionKind.BUILD, ActionKind.SIMULATE, ActionKind.RUN_BENCHMARK}:
            if not command.strip():
                return SafetyDecision(Decision.REPAIR, "missing command for executable action")

        return SafetyDecision(Decision.ALLOW, "policy checks passed")
