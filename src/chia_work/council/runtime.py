"""Runtime boundaries: fixed capabilities, limits, and template construction."""

from __future__ import annotations

from dataclasses import dataclass

from .agents import L0Template, L1CoordinatorTemplate, L1SynthesisTemplate, L2Template, L3Template
from .schemas import CapabilityGrant, CapabilitySpec, utc_now


FIXED_CAPABILITIES = (
    "READ_ARTIFACT", "WRITE_ARTIFACT", "REQUEST_L3", "REVIEW_PROPOSAL",
    "REQUEST_EXECUTION", "VETO", "READ_OBSERVATION",
)


@dataclass(frozen=True)
class RuntimeLimits:
    max_cycles: int = 2
    max_l2_per_cycle: int = 4
    max_l3_per_l2: int = 4
    max_total_agent_invocations: int = 20
    max_model_calls: int = 8
    max_wall_time: int = 300
    max_retries_per_task: int = 1

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def capability_specs(cycle_id: str) -> list[CapabilitySpec]:
    descriptions = {
        "READ_ARTIFACT": "Read an explicitly referenced artifact",
        "WRITE_ARTIFACT": "Write a new immutable artifact",
        "REQUEST_L3": "Request a leaf session through L1",
        "REVIEW_PROPOSAL": "Independently review a proposal",
        "REQUEST_EXECUTION": "Request a validated CHIA action",
        "VETO": "Veto a proposal within granted authority",
        "READ_OBSERVATION": "Read an execution observation",
    }
    return [CapabilitySpec(id=f"cap-{name.lower()}", cycle_id=cycle_id, creator="l1-coordinator", created_at=utc_now(), name=name, description=descriptions[name], delegable=name in {"READ_ARTIFACT", "WRITE_ARTIFACT", "REQUEST_L3"}) for name in FIXED_CAPABILITIES]


def grant(cycle_id: str, subject_id: str, capabilities: list[str], granted_by: str) -> CapabilityGrant:
    unknown = set(capabilities) - set(FIXED_CAPABILITIES)
    if unknown:
        raise ValueError(f"unknown capabilities: {sorted(unknown)}")
    return CapabilityGrant(id=f"grant-{subject_id}", cycle_id=cycle_id, creator=granted_by, created_at=utc_now(), subject_id=subject_id, capabilities=capabilities, granted_by=granted_by, delegable_capabilities=[c for c in capabilities if c in {"READ_ARTIFACT", "WRITE_ARTIFACT", "REQUEST_L3"}])


def template(level: str, instance_id: str):
    if level == "L0":
        return L0Template(instance_id)
    if level == "L1_COORDINATOR":
        return L1CoordinatorTemplate(instance_id)
    if level == "L1_SYNTHESIS":
        return L1SynthesisTemplate(instance_id)
    if level == "L2":
        return L2Template(instance_id)
    if level == "L3":
        return L3Template(instance_id)
    raise ValueError(f"unknown fixed template: {level}")

