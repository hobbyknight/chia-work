"""Bounded Gemini-led TAKEOVER_GATE runner."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .actions import ActionKind, TypedAction
from .council.artifacts import ArtifactStore
from .bridge.council_chia_bridge import validate_request
from .council.agents import ADKJsonAgent, L0Template, L1SynthesisTemplate, L2Template, L3Template
from .council.governance import Governance
from .council.harness import ident
from .council.schemas import (
    AgentInstance, ArtifactRef, CapabilityGrant, Cycle, Direction,
    ExecutionObservation, ExecutionRequest, IndependentReview,
    InputArtifactRefs, L0Decision, L1Synthesis, LeaderReport, Mission,
    OutputContract, Proposal, RoleSpec, TaskSpec, WorkerResult, utc_now,
)
from .council.runtime import grant
from .safety import Decision, SafetyGate
from .observability import ExecutionLifecycle
from .runtime_grounding import execution_grounding_context


TAKEOVER_LIMITS: dict[str, int | float] = {
    "max_cycles": 2, "max_l2_per_cycle": 4, "max_l3_per_l2": 4,
    "max_total_agent_invocations": 24, "max_model_calls": 20,
    "max_wall_time": 1800, "max_retries_per_task": 1,
}
ROLE_CAPABILITIES = {"READ_ARTIFACT", "WRITE_ARTIFACT", "REQUEST_L3"}
REVIEW_FUNCTIONS = ("safety", "specification", "technical feasibility", "evidence and provenance")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoleDraft(StrictModel):
    name: str = Field(min_length=1)
    mission: str = Field(min_length=1)
    capabilities: list[str]
    max_l3: int = Field(ge=1, le=4)


class InitialDirectionOutput(StrictModel):
    objective: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    roles: list[RoleDraft] = Field(min_length=2, max_length=4)
    decision: Literal["CONTINUE", "COMPLETE"]
    next_direction: str = Field(min_length=1)


class TaskDraft(StrictModel):
    task: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class TaskOutput(StrictModel):
    tasks: list[TaskDraft] = Field(min_length=1, max_length=4)


class LeafOutput(StrictModel):
    status: Literal["PASS", "FAIL", "WARN"]
    summary: str = Field(min_length=1)
    analysis: str = Field(min_length=1)
    evidence: dict[str, Any]


class LeaderOutput(StrictModel):
    status: Literal["PASS", "FAIL", "WARN"]
    conclusion: str = Field(min_length=1)
    warnings: list[str]


class ActionDraft(StrictModel):
    action_kind: str = Field(min_length=1)
    target: str = Field(min_length=1)
    payload: dict[str, Any]


class ProposalOutput(StrictModel):
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    request_execution: bool
    typed_action: ActionDraft | None = None


class ReviewOutput(StrictModel):
    verdict: Literal["APPROVE", "REJECT", "ABSTAIN"]
    rationale: str = Field(min_length=1)
    veto: bool
    veto_reason: str | None = None


class SynthesisOutput(StrictModel):
    state_summary: str = Field(min_length=1)
    open_questions: list[str]
    observation_interpretation: str = Field(min_length=1)


class NextDirectionOutput(StrictModel):
    objective: str = Field(min_length=1)
    next_direction: str = Field(min_length=1)
    requested_roles: list[str] = Field(max_length=4)
    rationale: str = Field(min_length=1)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def safe_action_surface() -> dict[str, Any]:
    return {
        "action_kinds": [kind.value for kind in ActionKind],
        "safety_gate_default_allowed": [kind.value for kind in sorted(SafetyGate.DEFAULT_ALLOWED, key=lambda item: item.value)],
        "classification": {
            "BUILD": "potentially mutating; not exposed",
            "SIMULATE": "execution-capable; not exposed without a specific non-mutating policy",
            "MODIFY_CONFIG": "system/config mutation; not exposed",
            "RUN_BENCHMARK": "potentially scientific execution; only exact identity validation is exposed",
            "SHELL": "arbitrary system command; not exposed",
        },
        "exposed": {
            "action_kind": ActionKind.RUN_BENCHMARK.value,
            "target": "chia-local-smoke",
            "payload_constraints": {"command": "chia:identity", "payload_max_length": 256, "no_system_mutation": True, "no_hardware": True},
        },
    }


def exposed_typed_action_contract() -> dict[str, Any]:
    return {
        "allowed_top_level_fields": ["action_kind", "target", "payload"],
        "allowed_payload_fields": ["command", "payload"],
        "required_payload_fields": ["command"],
        "optional_payload_fields": ["payload"],
        "fixed_values": {
            "action_kind": ActionKind.RUN_BENCHMARK.value,
            "target": "chia-local-smoke",
            "payload.command": "chia:identity",
        },
        "payload_constraints": {"payload_max_length": 256},
        "unknown_fields": "invalid",
    }


def validate_exposed_action(draft: ActionDraft) -> TypedAction:
    if draft.action_kind != ActionKind.RUN_BENCHMARK.value:
        raise ValueError("action kind is outside the exposed non-destructive surface")
    if draft.target != "chia-local-smoke":
        raise ValueError("action target is outside the exposed non-destructive surface")
    if set(draft.payload) - {"command", "payload"}:
        raise ValueError("typed action contains fields outside the exposed surface")
    if draft.payload.get("command") != "chia:identity":
        raise ValueError("only the typed chia:identity operation is exposed")
    payload = draft.payload.get("payload", "")
    if not isinstance(payload, str) or len(payload) > 256:
        raise ValueError("identity payload must be a string of at most 256 characters")
    action = TypedAction(ActionKind.RUN_BENCHMARK, "chia-local-smoke", dict(draft.payload))
    decision = SafetyGate().evaluate(action)
    if decision.decision != Decision.ALLOW:
        raise ValueError(f"exposed action failed SafetyGate: {decision.decision.value}: {decision.reason}")
    return action


class GateRunner:
    def __init__(self, root: str | Path, mission_objective: str):
        self.root = Path(root)
        self.store = ArtifactStore(self.root)
        self.mission_objective = mission_objective
        self.run_id = self.root.name
        self.model_calls = 0
        self.invocations = 0
        self.started = time.monotonic()
        self.lifecycle = ExecutionLifecycle(self.run_id, self.root / ".lifecycle-events.jsonl")
        self._phase = "INITIALIZATION"
        self._proposal_id: str | None = None
        self._decision_id: str | None = None
        self._request_id: str | None = None
        self._observability_errors: list[str] = []
        (self.root / "traces").mkdir(parents=True, exist_ok=True)
        self.interventions = {
            "human_stage_selection_count": 0,
            "chatgpt_scientific_decision_count": 0,
            "codex_scientific_decision_count": 0,
            "manual_typed_action_repair_count": 0,
            "manual_role_assignment_count": 0,
            "manual_task_assignment_count": 0,
            "manual_veto_override_count": 0,
        }

    def _observe(self, operation, *args, **kwargs):
        """Best-effort evidence write that never changes the gate decision."""
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            self._observability_errors.append(f"{type(exc).__name__}: {exc}")
            return None

    def _emit_lifecycle(self, event_type: str, **fields):
        return self._observe(self.lifecycle.append, event_type, **fields)

    def _terminal_lifecycle(self, status: str, phase: str, reason: str, **references):
        return self._observe(self.lifecycle.terminal, status, phase, reason, **references)

    def _check_limits(self) -> None:
        if time.monotonic() - self.started > TAKEOVER_LIMITS["max_wall_time"]:
            raise RuntimeError("max_wall_time exceeded")
        if self.model_calls >= TAKEOVER_LIMITS["max_model_calls"]:
            raise RuntimeError("max_model_calls exceeded")

    def _call(self, agent: ADKJsonAgent, prompt: str, output_type: type[StrictModel], trace: str) -> StrictModel:
        self._check_limits()
        self.model_calls += 1
        result = agent.call(prompt, output_type, max_retries=int(TAKEOVER_LIMITS["max_retries_per_task"]))
        self._trace(trace, {"model_call_index": self.model_calls, "output": result.model_dump(mode="json")})
        return result

    def _trace(self, name: str, value: dict[str, Any]) -> None:
        with (self.root / "traces" / f"{name}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(_json({"timestamp": utc_now(), **value}) + "\n")

    def _write_instance(self, cycle: Cycle, instance: AgentInstance, path: str, lineage: list[str]) -> ArtifactRef:
        return self.store.write_json(path, instance, artifact_id=instance.id, cycle_id=cycle.id, creator=instance.creator, parent_id=instance.parent_id, lineage_refs=lineage)

    def _write_role(self, cycle: Cycle, draft: RoleDraft, parent_id: str) -> tuple[RoleSpec, ArtifactRef]:
        unknown = set(draft.capabilities) - ROLE_CAPABILITIES
        if unknown:
            raise ValueError(f"L0 requested capabilities outside role grant: {sorted(unknown)}")
        role = RoleSpec(id=ident("role"), cycle_id=cycle.id, creator="l0", created_at=utc_now(), parent_id=parent_id, name=draft.name, mission=draft.mission, capabilities=draft.capabilities, max_l3=draft.max_l3)
        ref = self.store.write_json(f"cycles/{cycle.id}/l1/roles/{role.id}.json", role, artifact_id=role.id, cycle_id=cycle.id, creator=role.creator, parent_id=parent_id, lineage_refs=[parent_id])
        return role, ref

    def _write_task(self, cycle: Cycle, l2: AgentInstance, role: RoleSpec, draft: TaskDraft) -> tuple[TaskSpec, ArtifactRef]:
        task = TaskSpec(id=ident("task"), cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), parent_id=l2.id, task=draft.task, inputs=InputArtifactRefs(id=ident("inputs"), cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), refs=[]), tools=["read_artifact"], output_contract=OutputContract(id=ident("contract"), cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), required_files=["result.json", "analysis.md", "evidence.json", "manifest.json"]), assigned_role_id=role.id)
        ref = self.store.write_json(f"cycles/{cycle.id}/l2/{l2.id}/tasks/{task.id}.json", task, artifact_id=task.id, cycle_id=cycle.id, creator=l2.id, parent_id=l2.id, lineage_refs=[role.id])
        return task, ref

    def _write_l3(self, cycle: Cycle, l2: AgentInstance, task: TaskSpec, output: LeafOutput, *, l3_id: str) -> list[ArtifactRef]:
        l3 = AgentInstance(id=l3_id, cycle_id=cycle.id, creator="l1-coordinator", created_at=utc_now(), parent_id=l2.id, level="L3", template="L3", task_spec_id=task.id)
        base = f"cycles/{cycle.id}/l3/{l3.id}"
        self._write_instance(cycle, l3, f"{base}/agent.json", [task.id])
        evidence_id = ident("evidence")
        result = WorkerResult(id=ident("result"), cycle_id=cycle.id, creator=l3.id, created_at=utc_now(), parent_id=task.id, task_spec_id=task.id, status=output.status, summary=output.summary, evidence_refs=[evidence_id])
        refs = [self.store.write_json(f"{base}/result.json", result, artifact_id=result.id, cycle_id=cycle.id, creator=l3.id, parent_id=task.id, lineage_refs=[task.id])]
        analysis = self.store.write_text(f"{base}/analysis.md", output.analysis, artifact_id=ident("analysis"), cycle_id=cycle.id, creator=l3.id, parent_id=task.id, lineage_refs=[result.id])
        refs.append(analysis)
        evidence = {"schema_version": 1, "id": evidence_id, "cycle_id": cycle.id, "creator": l3.id, "created_at": utc_now(), "parent_id": task.id, "artifact_refs": [ref.id for ref in refs], "lineage_refs": [task.id], "evidence": output.evidence}
        refs.append(self.store.write_json(f"{base}/evidence.json", evidence, artifact_id=evidence_id, cycle_id=cycle.id, creator=l3.id, parent_id=task.id, lineage_refs=[task.id]))
        manifest = {"schema_version": 1, "id": ident("l3-manifest"), "cycle_id": cycle.id, "creator": l3.id, "created_at": utc_now(), "parent_id": task.id, "artifact_refs": [ref.id for ref in refs], "lineage_refs": [task.id], "files": [ref.path for ref in refs]}
        refs.append(self.store.write_json(f"{base}/manifest.json", manifest, artifact_id=manifest["id"], cycle_id=cycle.id, creator=l3.id, parent_id=task.id, lineage_refs=[ref.id for ref in refs]))
        return refs

    def _write_l2_report(self, cycle: Cycle, l2: AgentInstance, role: RoleSpec, worker_refs: list[ArtifactRef], output: LeaderOutput) -> list[ArtifactRef]:
        report = LeaderReport(id=ident("leader-report"), cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), parent_id=l2.id, role_spec_id=role.id, status=output.status, worker_result_refs=[ref.id for ref in worker_refs if ref.path.endswith("result.json")], conclusion=output.conclusion, warnings=output.warnings)
        base = f"cycles/{cycle.id}/l2/{l2.id}"
        refs = [self.store.write_json(f"{base}/leader_report.json", report, artifact_id=report.id, cycle_id=cycle.id, creator=l2.id, parent_id=l2.id, lineage_refs=[ref.id for ref in worker_refs])]
        refs.append(self.store.write_text(f"{base}/summary.md", output.conclusion, artifact_id=ident("l2-summary"), cycle_id=cycle.id, creator=l2.id, parent_id=report.id, lineage_refs=[report.id]))
        refs.append(self.store.write_json(f"{base}/evidence_refs.json", {"schema_version": 1, "id": ident("l2-evidence"), "cycle_id": cycle.id, "creator": l2.id, "created_at": utc_now(), "parent_id": report.id, "artifact_refs": [ref.id for ref in worker_refs], "lineage_refs": [ref.id for ref in worker_refs]}, artifact_id=ident("l2-evidence-artifact"), cycle_id=cycle.id, creator=l2.id, parent_id=report.id, lineage_refs=[ref.id for ref in worker_refs]))
        refs.append(self.store.write_json(f"{base}/manifest.json", {"schema_version": 1, "id": ident("l2-manifest"), "cycle_id": cycle.id, "creator": "l1-coordinator", "created_at": utc_now(), "parent_id": report.id, "artifact_refs": [ref.id for ref in refs], "lineage_refs": [report.id]}, artifact_id=ident("l2-manifest-artifact"), cycle_id=cycle.id, creator="l1-coordinator", parent_id=report.id, lineage_refs=[report.id]))
        return refs

    def _write_l1(self, cycle: Cycle, leader_refs: list[ArtifactRef], output: SynthesisOutput, observation_ref: str) -> ArtifactRef:
        synthesis = L1Synthesis(id=ident("l1-synthesis"), cycle_id=cycle.id, creator="l1-synthesis", created_at=utc_now(), parent_id=cycle.id, status="PASS", leader_report_refs=[ref.id for ref in leader_refs if ref.path.endswith("leader_report.json")], state_summary=output.state_summary, open_questions=output.open_questions, active_veto_refs=[], lineage_refs=[ref.id for ref in leader_refs] + [observation_ref])
        refs = [self.store.write_json(f"cycles/{cycle.id}/l1/state.json", synthesis, artifact_id=synthesis.id, cycle_id=cycle.id, creator=synthesis.creator, parent_id=cycle.id, lineage_refs=synthesis.lineage_refs)]
        for name, value in [("task_graph.json", {"observation_interpretation": output.observation_interpretation}), ("open_questions.json", {"questions": output.open_questions}), ("active_vetoes.json", {"vetoes": []})]:
            payload = {"schema_version": 1, "id": ident(name[:-5]), "cycle_id": cycle.id, "creator": "l1-synthesis", "created_at": utc_now(), "parent_id": synthesis.id, "artifact_refs": [synthesis.id], "lineage_refs": [synthesis.id], **value}
            refs.append(self.store.write_json(f"cycles/{cycle.id}/l1/{name}", payload, artifact_id=payload["id"], cycle_id=cycle.id, creator="l1-synthesis", parent_id=synthesis.id, lineage_refs=[synthesis.id]))
        refs.append(self.store.write_text(f"cycles/{cycle.id}/l1/cycle_summary.md", output.state_summary + "\n\n" + output.observation_interpretation, artifact_id=ident("cycle-summary"), cycle_id=cycle.id, creator="l1-synthesis", parent_id=synthesis.id, lineage_refs=[synthesis.id, observation_ref]))
        return refs[0]

    def _write_preproposal_l1(self, cycle: Cycle, leader_refs: list[ArtifactRef], output: SynthesisOutput) -> ArtifactRef:
        lineage_refs = [ref.id for ref in leader_refs]
        synthesis = L1Synthesis(
            id=ident("l1-pre-proposal-synthesis"),
            cycle_id=cycle.id,
            creator="l1-synthesis",
            created_at=utc_now(),
            parent_id=cycle.id,
            status="PASS",
            leader_report_refs=[ref.id for ref in leader_refs if ref.path.endswith("leader_report.json")],
            state_summary=output.state_summary,
            open_questions=output.open_questions,
            active_veto_refs=[],
            lineage_refs=lineage_refs,
        )
        return self.store.write_json(
            f"cycles/{cycle.id}/l1/pre-proposal-state.json",
            synthesis,
            artifact_id=synthesis.id,
            cycle_id=cycle.id,
            creator=synthesis.creator,
            parent_id=cycle.id,
            lineage_refs=lineage_refs,
        )

    def _execute_once(self, request: ExecutionRequest, decision: Any, capability: CapabilityGrant) -> dict[str, Any]:
        payload = {"execution_request": request.model_dump(mode="json"), "decision_record": decision.model_dump(mode="json"), "capability_grant": capability.model_dump(mode="json")}
        validate_request(payload)
        chia_python = os.environ.get("CHIA_PYTHON", "/home/devstar7706/chia-work/.venv/bin/python")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        env["SAFEAGENT_LIFECYCLE_PATH"] = str(self.lifecycle.stream_path)
        env["SAFEAGENT_RUN_ID"] = self.run_id
        env["SAFEAGENT_EXECUTION_REQUEST_ID"] = request.id
        proc = subprocess.run([chia_python, "-m", "chia_work.bridge.takeover_executor"], input=_json(payload), text=True, capture_output=True, timeout=180, env=env, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"CHIA worker failed: rc={proc.returncode} stderr={proc.stderr[-2000:]}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"CHIA worker returned non-JSON stdout: {proc.stdout[-2000:]}") from exc

    def run(self) -> dict[str, Any]:
        self._emit_lifecycle("run_started", phase="INITIALIZATION", status="STARTED")
        try:
            result = self._run()
        except Exception as exc:
            try:
                counts = self.lifecycle.counters()
            except Exception as lifecycle_exc:
                self._observability_errors.append(f"{type(lifecycle_exc).__name__}: {lifecycle_exc}")
                counts = {"execution_boundary_entries": 0}
            boundary_entered = counts["execution_boundary_entries"] > 0
            if self._phase == "VERIFIER":
                terminal_status = "VERIFICATION_FAILED"
            elif boundary_entered:
                terminal_status = "EXECUTION_FAILED"
            else:
                terminal_status = "REJECTED" if self._phase in {"ACTION_VALIDATION", "EXECUTION_DISPATCH", "SAFETY_GATE"} else "STOPPED"
            self._terminal_lifecycle(
                terminal_status,
                self._phase,
                f"{type(exc).__name__}: {exc}",
                exception_type=type(exc).__name__,
                proposal_id=self._proposal_id,
                decision_id=self._decision_id,
                request_id=self._request_id,
            )
            try:
                self.lifecycle.persist(self.store)
            except Exception:
                # Evidence persistence is best-effort here; preserve the pre-existing exception.
                pass
            raise
        status = result.get("status", "STOPPED")
        if status == "TAKEOVER_REJECTED_BY_GEMINI_VETO":
            terminal_status, phase, reason = "REJECTED", "GOVERNANCE", status
        elif status == "STOP_NO_MODEL_EXECUTION_REQUEST":
            terminal_status, phase, reason = "STOPPED", "PROPOSAL", status
        elif status == "TAKEOVER_GATE_PASS":
            terminal_status, phase, reason = "COMPLETED", "COMPLETE", status
        else:
            terminal_status, phase, reason = status, self._phase, status
        self._terminal_lifecycle(
            terminal_status, phase, reason,
            proposal_id=result.get("proposal_id") or self._proposal_id,
            decision_id=result.get("decision_id") or self._decision_id,
            request_id=result.get("request_id") or self._request_id,
        )
        try:
            refs = self.lifecycle.persist(self.store)
            persistence_error = None
        except Exception as exc:
            # Instrumentation storage failure must not rewrite an existing gate status.
            refs = []
            persistence_error = f"{type(exc).__name__}: {exc}"
        try:
            result["execution_counters"] = self.lifecycle.counters()
        except Exception as exc:
            result["execution_counters"] = {"execution_requests_created": 0, "execution_boundary_entries": 0, "execution_completions": 0, "execution_failures": 0}
            self._observability_errors.append(f"{type(exc).__name__}: {exc}")
        result["lifecycle_artifact_refs"] = [ref.id for ref in refs]
        if persistence_error is not None:
            result["lifecycle_persistence_error"] = persistence_error
        if self._observability_errors:
            result["lifecycle_observability_errors"] = list(self._observability_errors)
        return result

    def _run(self) -> dict[str, Any]:
        self._phase = "HIERARCHY"
        mission_id = ident("mission")
        cycle_id = ident("cycle")
        mission = Mission(id=mission_id, cycle_id=cycle_id, creator="user", created_at=utc_now(), run_id=self.run_id, objective=self.mission_objective)
        cycle = Cycle(id=cycle_id, cycle_id=cycle_id, creator="l1-coordinator", created_at=utc_now(), parent_id=mission.id, run_id=self.run_id, index=0, limits=TAKEOVER_LIMITS)
        mission_ref = self.store.write_json("mission/mission.json", mission, artifact_id=mission.id, cycle_id=cycle.id, creator=mission.creator)
        self.store.write_json(f"cycles/{cycle.id}/cycle.json", cycle, artifact_id=cycle.id, cycle_id=cycle.id, creator=cycle.creator, parent_id=mission.id, lineage_refs=[mission.id])
        self._emit_lifecycle("cycle_started", phase="HIERARCHY", status="OPEN", cycle_id=cycle.id, mission_id=mission.id)
        self.store.write_json("mission/action-surface.json", safe_action_surface(), artifact_id=ident("action-surface"), cycle_id=cycle.id, creator="l1-coordinator", parent_id=mission.id, lineage_refs=[mission.id])
        self._trace("role-trace", {"event": "autonomous_window_start", "mission_id": mission.id, "cycle_id": cycle.id, "limits": TAKEOVER_LIMITS})

        l0_agent = ADKJsonAgent(L0Template("l0-takeover"))
        initial = self._call(l0_agent, _json({"mission": mission.objective, "limits": TAKEOVER_LIMITS, "fixed_role_capabilities": sorted(ROLE_CAPABILITIES), "instruction": "Determine the specialist roles required for this mission. Choose the roles yourself. Use 2-4 roles and one bounded task per role is sufficient for this gate. Do not choose hardware, experiments, or a next scientific stage."}), InitialDirectionOutput, "role-trace")
        if initial.decision != "CONTINUE":
            raise RuntimeError("L0 ended the gate before the required takeover chain")
        direction = Direction(id=ident("direction"), cycle_id=cycle.id, creator="l0", created_at=utc_now(), parent_id=mission.id, objective=initial.objective, requested_roles=[role.name for role in initial.roles], next_direction=initial.next_direction)
        direction_ref = self.store.write_json(f"cycles/{cycle.id}/l0/direction.json", direction, artifact_id=direction.id, cycle_id=cycle.id, creator="l0", parent_id=mission.id, lineage_refs=[mission_ref.id])
        self.store.write_json(f"cycles/{cycle.id}/l0/decision.json", L0Decision(id=ident("l0-decision"), cycle_id=cycle.id, creator="l0", created_at=utc_now(), parent_id=direction.id, direction_id=direction.id, decision=initial.decision, reason=initial.rationale), artifact_id=ident("l0-decision-artifact"), cycle_id=cycle.id, creator="l0", parent_id=direction.id, lineage_refs=[direction_ref.id])

        roles: list[RoleSpec] = []
        for draft in initial.roles:
            role, _ = self._write_role(cycle, draft, direction.id)
            roles.append(role)
        self._trace("role-trace", {"event": "l0_roles", "direction_id": direction.id, "roles": [role.model_dump(mode="json") for role in roles]})

        l2_reports: list[ArtifactRef] = []
        l2_report_models: list[LeaderReport] = []
        for role in roles:
            self.invocations += 1
            if self.invocations > TAKEOVER_LIMITS["max_total_agent_invocations"]:
                raise RuntimeError("max_total_agent_invocations exceeded")
            l2_id = ident("l2")
            l2_grant = grant(cycle.id, l2_id, role.capabilities, "l1-coordinator") if role.capabilities else None
            l2 = AgentInstance(id=l2_id, cycle_id=cycle.id, creator="l1-coordinator", created_at=utc_now(), parent_id=role.id, level="L2", template="L2", role_spec_id=role.id, capability_grant_id=None if l2_grant is None else l2_grant.id)
            self._write_instance(cycle, l2, f"cycles/{cycle.id}/l2/{l2.id}/agent.json", [role.id])
            l2_agent = ADKJsonAgent(L2Template(l2.id))
            task_output = self._call(l2_agent, _json({"mission": mission.objective, "role": role.model_dump(mode="json"), "input_artifacts": [direction.id], "limits": TAKEOVER_LIMITS, "instruction": "Decompose your role into one bounded metadata-only leaf task for this gate. Do not execute CHIA and do not invent permissions."}), TaskOutput, "task-trace")
            if len(task_output.tasks) > 1:
                raise RuntimeError("L2 returned more than one task under the frozen model-call budget")
            task, _ = self._write_task(cycle, l2, role, task_output.tasks[0])
            self._trace("task-trace", {"event": "l2_tasks", "l2_id": l2.id, "role_id": role.id, "tasks": [task.model_dump(mode="json")]})
            self.invocations += 1
            l3_id = ident("l3")
            leaf_agent = ADKJsonAgent(L3Template(l3_id))
            leaf = self._call(leaf_agent, _json({"mission": mission.objective, "task": task.model_dump(mode="json"), "role": role.model_dump(mode="json"), "instruction": "Act as the leaf executor. Perform only a harmless metadata-only analysis using the supplied task. Return evidence, with no CHIA or system execution."}), LeafOutput, "task-trace")
            refs = self._write_l3(cycle, l2, task, leaf, l3_id=l3_id)
            l2_summary = self._call(l2_agent, _json({"mission": mission.objective, "role": role.model_dump(mode="json"), "task": task.model_dump(mode="json"), "l3_artifacts": [ref.model_dump(mode="json") for ref in refs], "execution_grounding": execution_grounding_context(cycle.id, self.lifecycle, self.store), "instruction": "Synthesize the L3 evidence for your role. Use execution_grounding for factual statements about runtime execution state; distinguish plans, requests, approval, execution, completion, and failure. Do not select a scientific stage."}), LeaderOutput, "task-trace")
            report_refs = self._write_l2_report(cycle, l2, role, refs, l2_summary)
            l2_reports.extend(report_refs)
            l2_report_models.append(LeaderReport.model_validate(self.store.read_json(report_refs[0])))
            self._trace("task-trace", {"event": "l2_report", "l2_id": l2.id, "report": self.store.read_json(report_refs[0])})

        preproposal_agent = ADKJsonAgent(L1SynthesisTemplate("l1-pre-proposal"))
        preproposal_output = self._call(
            preproposal_agent,
            _json({
                "mission": mission.objective,
                "direction": direction.model_dump(mode="json"),
                "l2_reports": [report.model_dump(mode="json") for report in l2_report_models],
                "execution_grounding": execution_grounding_context(cycle.id, self.lifecycle, self.store),
                "instruction": "Aggregate the L2 reports into a structured synthesis for L0 proposal review. Use execution_grounding for factual statements about runtime execution state; distinguish plans, requests, approval, execution, completion, and failure. Summarize supplied state and open questions only; do not choose a scientific stage or action.",
            }),
            SynthesisOutput,
            "governance-trace",
        )
        preproposal_ref = self._write_preproposal_l1(cycle, l2_reports, preproposal_output)
        proposal_execution_state = {
            "execution_request_created": False,
            "execution_attempted": False,
            "execution_observation_present": False,
        }
        self._phase = "PROPOSAL"
        proposal_output = self._call(
            l0_agent,
            _json({
                "mission": mission.objective,
                "direction": direction.model_dump(mode="json"),
                "l2_reports": [report.model_dump(mode="json") for report in l2_report_models],
                "l1_synthesis": preproposal_output.model_dump(mode="json"),
                "l1_synthesis_artifact": preproposal_ref.model_dump(mode="json"),
                "execution_state": proposal_execution_state,
                "action_surface": safe_action_surface(),
                "typed_action_contract": exposed_typed_action_contract(),
                "instruction": "Create one proposal based on the supplied reports and L1 synthesis. Only describe execution as having occurred if an ExecutionObservation artifact is actually supplied. At this proposal stage, no execution has occurred. If the mission requires a permitted execution and none has occurred, propose/request it through the typed action interface instead of narrating it as completed. Do not invent execution results. Return only fields defined by the TypedAction schema and the exact typed_action contract supplied here. Unknown top-level or payload fields are invalid. Do not add safety annotations, policy metadata, explanatory fields, or extra booleans such as no_hardware, no_system_mutation, safe, approved, or verified. Safety constraints are enforced externally by governance and SafetyGate, not by adding fields to TypedAction. Decide yourself whether the single exposed non-destructive typed action is justified. If requesting execution, provide a complete typed_action from the supplied action surface. Never provide shell, bash, ssh, sudo, rm, or arbitrary commands.",
            }),
            ProposalOutput,
            "governance-trace",
        )
        proposal = Proposal(id=ident("proposal"), cycle_id=cycle.id, creator="l0", created_at=utc_now(), parent_id=direction.id, title=proposal_output.title, payload={"rationale": proposal_output.rationale, "request_execution": proposal_output.request_execution, "typed_action": None if proposal_output.typed_action is None else proposal_output.typed_action.model_dump(mode="json")}, proposer_id="l0")
        self.store.write_json(f"cycles/{cycle.id}/governance/proposal.json", proposal, artifact_id=proposal.id, cycle_id=cycle.id, creator="l0", parent_id=direction.id, lineage_refs=[direction.id, preproposal_ref.id] + [ref.id for ref in l2_reports])
        self._proposal_id = proposal.id
        self._trace("governance-trace", {"event": "proposal", "proposal": proposal.model_dump(mode="json")})

        self._phase = "GOVERNANCE"
        governance = Governance(self.store, cycle.id)
        review_results: list[tuple[IndependentReview, ReviewOutput]] = []
        shared = {"mission": mission.objective, "proposal": proposal.model_dump(mode="json"), "shared_facts": {"action_surface": safe_action_surface(), "artifact_refs": [ref.id for ref in l2_reports]}}
        for function in REVIEW_FUNCTIONS:
            reviewer_id = f"reviewer-{uuid.uuid4().hex[:8]}"
            reviewer = ADKJsonAgent(L2Template(reviewer_id))
            review_output = self._call(reviewer, _json({**shared, "review_function": function, "instruction": "Review independently. This is the first review phase: do not infer or discuss any other reviewer. Set veto=true only if this proposal violates your granted review authority or safety boundary. Do not propose a replacement action."}), ReviewOutput, "review-trace")
            review = governance.commit_review(proposal, reviewer_id, review_output.verdict, review_output.rationale)
            self.store.write_json(f"cycles/{cycle.id}/reviews/commits/{review.id}.json", {"schema_version": 1, "id": review.id, "cycle_id": cycle.id, "creator": reviewer_id, "created_at": review.created_at, "parent_id": proposal.id, "artifact_refs": [], "lineage_refs": [proposal.id], "reviewer_id": reviewer_id, "commit_sha256": review.commit_sha256, "commit_only": True}, artifact_id=ident("review-commit"), cycle_id=cycle.id, creator=reviewer_id, parent_id=proposal.id, lineage_refs=[proposal.id])
            review_results.append((review, review_output))
            self._trace("review-trace", {"event": "commit", "reviewer_id": reviewer_id, "review_id": review.id, "commit_sha256": review.commit_sha256, "verdict_hidden": True})

        governance.reveal_all({review.reviewer_id for review, _ in review_results})
        review_refs: list[str] = []
        for review, review_output in review_results:
            review.revealed = True
            ref = self.store.write_json(f"cycles/{cycle.id}/reviews/revealed/{review.id}.json", review, artifact_id=review.id, cycle_id=cycle.id, creator=review.reviewer_id, parent_id=proposal.id, lineage_refs=[proposal.id])
            review_refs.append(ref.id)
            self._trace("review-trace", {"event": "reveal", "review_id": review.id, "reviewer_id": review.reviewer_id, "verdict": review.verdict, "veto": review_output.veto, "rationale": review.rationale})
            if review_output.veto:
                veto = governance.record_veto(proposal, review.reviewer_id, review_output.veto_reason or review_output.rationale, allowed=True)
                self.store.write_json(f"cycles/{cycle.id}/governance/veto-{veto.id}.json", veto, artifact_id=veto.id, cycle_id=cycle.id, creator=veto.vetoer_id, parent_id=proposal.id, lineage_refs=[review.id])
                self._trace("governance-trace", {"event": "veto", "veto": veto.model_dump(mode="json")})
        decision = governance.decide(proposal, review_refs)
        self._decision_id = decision.id
        self.store.write_json(f"cycles/{cycle.id}/decisions/{decision.id}.json", decision, artifact_id=decision.id, cycle_id=cycle.id, creator=decision.creator, parent_id=proposal.id, lineage_refs=review_refs + decision.veto_refs)
        self._trace("governance-trace", {"event": "decision", "decision": decision.model_dump(mode="json")})
        if decision.status != "APPROVED":
            return {"status": "TAKEOVER_REJECTED_BY_GEMINI_VETO", "decision_id": decision.id, "model_calls": self.model_calls, "interventions": self.interventions}
        if not proposal_output.request_execution or proposal_output.typed_action is None:
            return {"status": "STOP_NO_MODEL_EXECUTION_REQUEST", "proposal_id": proposal.id, "decision_id": decision.id, "model_calls": self.model_calls, "interventions": self.interventions}
        self._phase = "ACTION_VALIDATION"
        action = validate_exposed_action(proposal_output.typed_action)
        capability = grant(cycle.id, "l0", ["REQUEST_EXECUTION"], "l1-governance")
        self.store.write_json(f"cycles/{cycle.id}/execution/capability-grant.json", capability, artifact_id=capability.id, cycle_id=cycle.id, creator=capability.granted_by, parent_id=decision.id, lineage_refs=[decision.id])
        request = ExecutionRequest(id=ident("execution-request"), cycle_id=cycle.id, creator="l0", created_at=utc_now(), parent_id=decision.id, decision_record_id=decision.id, typed_action={"schema_version": 1, "action_kind": action.kind.value, "target": action.target, "payload": action.params}, requested_by="l0", capability_grant_id=capability.id, lineage_refs=[decision.id, proposal.id])
        request_ref = self.store.write_json(f"cycles/{cycle.id}/execution/request.json", request, artifact_id=request.id, cycle_id=cycle.id, creator=request.creator, parent_id=decision.id, lineage_refs=[decision.id, proposal.id])
        self._request_id = request.id
        self._emit_lifecycle(
            "execution_request_created", phase="REQUEST", status="REQUESTED",
            cycle_id=cycle.id, proposal_id=proposal.id, decision_id=decision.id,
            request_id=request.id, action_kind=action.kind.value, target=action.target,
        )
        self._trace("execution-trace", {"event": "request", "request": request.model_dump(mode="json")})
        self._phase = "EXECUTION_DISPATCH"
        result = self._execute_once(request, decision, capability)
        status = "EXECUTED" if result.get("status") == "EXECUTED" else "REJECTED"
        if result.get("backend") == "safety-gate":
            self._phase = "SAFETY_GATE"
            self._terminal_lifecycle(
                "REJECTED", "SAFETY_GATE", str(result.get("reason", "SafetyGate denied action")),
                cycle_id=cycle.id, proposal_id=proposal.id, decision_id=decision.id,
                request_id=request.id, action_ref=action.target,
            )
        elif status != "EXECUTED":
            self._phase = "EXECUTION_BACKEND"
        observation = ExecutionObservation(id=ident("execution-observation"), cycle_id=cycle.id, creator="chia-bridge", created_at=utc_now(), parent_id=request.id, execution_request_id=request.id, status=status, observation=result, hardware_executed=bool(result.get("hardware_executed", False)), lineage_refs=[request.id, decision.id])
        observation_ref = self.store.write_json(f"cycles/{cycle.id}/execution/observation.json", observation, artifact_id=observation.id, cycle_id=cycle.id, creator=observation.creator, parent_id=request.id, lineage_refs=[request.id, decision.id])
        self._trace("execution-trace", {"event": "observation", "observation": observation.model_dump(mode="json")})
        if status != "EXECUTED" or not result.get("verified", True):
            if status == "EXECUTED" and not result.get("verified", True):
                self._phase = "VERIFIER"
            raise RuntimeError("CHIA execution or verification failed")
        synthesis_agent = ADKJsonAgent(L2Template("l1-synthesis-takeover"))
        synthesis = self._call(synthesis_agent, _json({"mission": mission.objective, "l2_reports": [report.model_dump(mode="json") for report in l2_report_models], "decision": decision.model_dump(mode="json"), "observation": observation.model_dump(mode="json"), "execution_grounding": execution_grounding_context(cycle.id, self.lifecycle, self.store), "instruction": "Synthesize the cycle and supplied observation. Use execution_grounding as authoritative runtime state; distinguish plans, requests, approval, boundary entry, completion, and failure. Report open questions; do not select the next scientific stage."}), SynthesisOutput, "governance-trace")
        synthesis_ref = self._write_l1(cycle, l2_reports, synthesis, observation_ref.id)
        next_output = self._call(l0_agent, _json({"mission": mission.objective, "l1_synthesis": synthesis.model_dump(mode="json"), "decision": decision.model_dump(mode="json"), "observation": observation.model_dump(mode="json"), "instruction": "Read the real observation and synthesize a next direction yourself. Do not execute it. The gate ends after this output."}), NextDirectionOutput, "governance-trace")
        next_direction = Direction(id=ident("next-direction"), cycle_id=f"{cycle.id}-next", creator="l0", created_at=utc_now(), parent_id=observation.id, objective=next_output.objective, requested_roles=next_output.requested_roles, next_direction=next_output.next_direction, lineage_refs=[observation_ref.id, synthesis_ref.id])
        next_ref = self.store.write_json(f"cycles/{cycle.id}/l0/next-direction.json", next_direction, artifact_id=next_direction.id, cycle_id=cycle.id, creator="l0", parent_id=observation.id, lineage_refs=[observation_ref.id, synthesis_ref.id])
        self._trace("governance-trace", {"event": "next_direction", "next_direction": next_direction.model_dump(mode="json")})
        return {"status": "TAKEOVER_GATE_PASS", "mission_id": mission.id, "direction_id": direction.id, "proposal_id": proposal.id, "decision_id": decision.id, "request_id": request.id, "observation_id": observation.id, "next_direction_id": next_ref.id, "model_calls": self.model_calls, "interventions": self.interventions, "hardware_executed": observation.hardware_executed}


def run_gate(root: str | Path, mission_objective: str) -> dict[str, Any]:
    return GateRunner(root, mission_objective).run()


def main() -> int:
    run_id = os.environ.get("TAKEOVER_RUN_ID", f"takeover-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}")
    root = Path(os.environ.get("TAKEOVER_RUN_ROOT", "/tmp")) / run_id
    objective = os.environ.get("TAKEOVER_MISSION", "Evaluate the current SafeAgent state, organize the required roles, verify one bounded non-destructive CHIA identity path, read the observation, and determine a suitable next direction without executing it.")
    try:
        result = run_gate(root, objective)
    except Exception as exc:
        print(json.dumps({"status": "STOP", "error_type": type(exc).__name__, "error": str(exc), "run_root": str(root)}, sort_keys=True))
        return 1
    print(json.dumps({**result, "run_root": str(root)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
