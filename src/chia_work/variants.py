from __future__ import annotations

from dataclasses import dataclass

from .safety import SafetyGate


@dataclass(frozen=True)
class VariantSpec:
    name: str
    safety_enabled: bool
    semantic_policy_enabled: bool
    verification_enabled: bool
    recovery_enabled: bool
    description: str

    def make_gate(self) -> SafetyGate:
        return SafetyGate(semantic_enabled=self.semantic_policy_enabled)


VARIANTS: dict[str, VariantSpec] = {
    "U0": VariantSpec(
        name="U0",
        safety_enabled=False,
        semantic_policy_enabled=False,
        verification_enabled=False,
        recovery_enabled=False,
        description="Ungarded baseline: execute the proposed typed action without safety or verification.",
    ),
    "S1": VariantSpec(
        name="S1",
        safety_enabled=True,
        semantic_policy_enabled=False,
        verification_enabled=False,
        recovery_enabled=False,
        description="Generic pre-execution checks only; no target-specific semantic policy.",
    ),
    "S2": VariantSpec(
        name="S2",
        safety_enabled=True,
        semantic_policy_enabled=True,
        verification_enabled=False,
        recovery_enabled=False,
        description="Typed target-specific semantic policy before execution.",
    ),
    "S3": VariantSpec(
        name="S3",
        safety_enabled=True,
        semantic_policy_enabled=True,
        verification_enabled=True,
        recovery_enabled=False,
        description="S2 plus post-execution verification/oracles.",
    ),
    "S4": VariantSpec(
        name="S4",
        safety_enabled=True,
        semantic_policy_enabled=True,
        verification_enabled=True,
        recovery_enabled=True,
        description="S3 plus feedback-driven repair/retry.",
    ),
}


def get_variant(name: str) -> VariantSpec:
    try:
        return VARIANTS[name]
    except KeyError as exc:
        raise ValueError(f"unknown variant {name!r}; expected one of {sorted(VARIANTS)}") from exc
