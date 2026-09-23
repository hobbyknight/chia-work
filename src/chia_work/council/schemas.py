"""Versioned, JSON-serializable contracts for the SafeAgent hierarchy."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: int = SCHEMA_VERSION
    id: str
    cycle_id: str
    creator: str
    created_at: str
    parent_id: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    lineage_refs: list[str] = Field(default_factory=list)

    def stable_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class Mission(Record):
    run_id: str
    objective: str
    status: Literal["OPEN", "COMPLETE", "STOPPED"] = "OPEN"


class Direction(Record):
    objective: str
    requested_roles: list[str]
    next_direction: str


class L0Decision(Record):
    direction_id: str
    decision: Literal["CONTINUE", "COMPLETE"]
    reason: str


class Cycle(Record):
    run_id: str
    index: int
    limits: dict[str, int | float]
    status: Literal["OPEN", "COMPLETE", "STOPPED"] = "OPEN"


class CapabilitySpec(Record):
    name: str
    description: str
    delegable: bool = False


class CapabilityGrant(Record):
    subject_id: str
    capabilities: list[str]
    granted_by: str
    delegable_capabilities: list[str] = Field(default_factory=list)


class InputArtifactRefs(Record):
    refs: list[str]


class OutputContract(Record):
    required_files: list[str]
    format: Literal["json", "text", "bundle"] = "bundle"


class RoleSpec(Record):
    name: str
    mission: str
    capabilities: list[str]
    max_l3: int
    constraints: dict[str, Any] = Field(default_factory=dict)


class TaskSpec(Record):
    task: str
    inputs: InputArtifactRefs
    tools: list[str]
    output_contract: OutputContract
    assigned_role_id: str


class AgentInstance(Record):
    level: Literal["L0", "L1", "L2", "L3"]
    template: Literal["L0", "L1_COORDINATOR", "L1_SYNTHESIS", "L2", "L3"]
    role_spec_id: str | None = None
    task_spec_id: str | None = None
    capability_grant_id: str | None = None


class ArtifactRef(Record):
    path: str
    sha256: str
    kind: str
    locked: bool = True


class WorkerResult(Record):
    status: Literal["PASS", "FAIL", "WARN"]
    task_spec_id: str
    summary: str
    evidence_refs: list[str]
    warnings: list[str] = Field(default_factory=list)
    veto_requested: bool = False
    next_required_input: str | None = None


class LeaderReport(Record):
    status: Literal["PASS", "FAIL", "WARN"]
    role_spec_id: str
    worker_result_refs: list[str]
    conclusion: str
    veto_requested: bool = False
    warnings: list[str] = Field(default_factory=list)


class L1Synthesis(Record):
    status: Literal["PASS", "FAIL", "WARN"]
    leader_report_refs: list[str]
    state_summary: str
    open_questions: list[str]
    active_veto_refs: list[str] = Field(default_factory=list)


class Proposal(Record):
    status: Literal["PROPOSED", "APPROVED", "REJECTED"] = "PROPOSED"
    title: str
    payload: dict[str, Any]
    proposer_id: str


class IndependentReview(Record):
    proposal_id: str
    reviewer_id: str
    verdict: Literal["APPROVE", "REJECT", "ABSTAIN"]
    rationale: str
    commit_sha256: str
    revealed: bool = False


class VetoRecord(Record):
    proposal_id: str
    vetoer_id: str
    reason: str
    valid: bool = True


class DecisionRecord(Record):
    proposal_id: str
    status: Literal["APPROVED", "REJECTED"]
    review_refs: list[str]
    veto_refs: list[str] = Field(default_factory=list)
    rationale: str
    immutable: bool = True


class ExecutionRequest(Record):
    decision_record_id: str
    typed_action: dict[str, Any]
    requested_by: str
    capability_grant_id: str


class ExecutionObservation(Record):
    execution_request_id: str
    status: Literal["VALIDATED", "EXECUTED", "REJECTED"]
    observation: dict[str, Any]
    hardware_executed: bool = False


def model_from_json(model_type: type[Record], raw: str) -> Record:
    return model_type.model_validate(json.loads(raw))
