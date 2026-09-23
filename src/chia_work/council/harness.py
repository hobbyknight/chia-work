"""Deterministic bootstrap harness used by local smoke tests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Iterable

from .agents import L0Template, L1CoordinatorTemplate, L1SynthesisTemplate, L2Template, L3Template
from .artifacts import ArtifactStore
from .schemas import (
    AgentInstance, ArtifactRef, CapabilityGrant, Cycle, Direction, InputArtifactRefs,
    L0Decision, L1Synthesis, LeaderReport, Mission, OutputContract, RoleSpec,
    TaskSpec, WorkerResult, utc_now,
)


def ident(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class BootstrapHarness:
    def __init__(self, root: str | Path, *, limits: dict[str, int | float] | None = None):
        self.store = ArtifactStore(root)
        self.limits = limits or {
            "max_cycles": 2, "max_l2_per_cycle": 4, "max_l3_per_l2": 4,
            "max_total_agent_invocations": 20, "max_model_calls": 8,
            "max_wall_time": 300, "max_retries_per_task": 1,
        }
        self.invocations = 0
        self.model_calls = 0

    def start(self, objective: str, run_id: str = "smoke-run") -> tuple[Mission, Cycle]:
        mission_id = ident("mission")
        cycle_id = ident("cycle")
        mission = Mission(id=mission_id, cycle_id=cycle_id, creator="user", created_at=utc_now(), run_id=run_id, objective=objective)
        cycle = Cycle(id=cycle_id, cycle_id=cycle_id, creator="l1-coordinator", created_at=utc_now(), parent_id=mission_id, run_id=run_id, index=0, limits=self.limits)
        self.store.write_json("mission/mission.json", mission, artifact_id=mission.id, cycle_id=cycle_id, creator=mission.creator)
        self.store.write_json(f"cycles/{cycle_id}/cycle.json", cycle, artifact_id=cycle.id, cycle_id=cycle_id, creator=cycle.creator, parent_id=mission_id, lineage_refs=[mission_id])
        return mission, cycle

    def write_l0_outputs(self, cycle: Cycle, direction: Direction, decision: L0Decision) -> tuple[ArtifactRef, ArtifactRef]:
        d = self.store.write_json(f"cycles/{cycle.id}/l0/direction.json", direction, artifact_id=direction.id, cycle_id=cycle.id, creator="l0", parent_id=direction.parent_id, lineage_refs=direction.lineage_refs)
        x = self.store.write_json(f"cycles/{cycle.id}/l0/decision.json", decision, artifact_id=decision.id, cycle_id=cycle.id, creator="l0", parent_id=direction.id, lineage_refs=[d.id])
        return d, x

    def make_roles(self, cycle: Cycle, names: Iterable[str]) -> list[RoleSpec]:
        names = list(names)
        if len(names) > int(self.limits["max_l2_per_cycle"]):
            raise RuntimeError("max_l2_per_cycle exceeded")
        roles = []
        for name in names:
            role = RoleSpec(id=ident("role"), cycle_id=cycle.id, creator="l0", created_at=utc_now(), parent_id=cycle.id, name=name, mission=f"Analyze the supplied harmless smoke objective as {name}", capabilities=["READ_ARTIFACT", "WRITE_ARTIFACT", "REQUEST_L3"], max_l3=int(self.limits["max_l3_per_l2"]))
            self.store.write_json(f"cycles/{cycle.id}/l1/roles/{role.id}.json", role, artifact_id=role.id, cycle_id=cycle.id, creator=role.creator, parent_id=cycle.id)
            roles.append(role)
        return roles

    def create_l2(self, cycle: Cycle, role: RoleSpec) -> AgentInstance:
        self._count_invocation()
        inst = AgentInstance(id=ident("l2"), cycle_id=cycle.id, creator="l1-coordinator", created_at=utc_now(), parent_id=role.id, level="L2", template="L2", role_spec_id=role.id)
        self.store.write_json(f"cycles/{cycle.id}/l2/{inst.id}/agent.json", inst, artifact_id=inst.id, cycle_id=cycle.id, creator=inst.creator, parent_id=role.id, lineage_refs=[role.id])
        return inst

    def make_tasks(self, cycle: Cycle, l2: AgentInstance, role: RoleSpec, tasks: Iterable[str]) -> list[TaskSpec]:
        task_names = list(tasks)
        if len(task_names) > role.max_l3:
            raise RuntimeError("max_l3_per_l2 exceeded")
        out = []
        for name in task_names:
            task = TaskSpec(id=ident("task"), cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), parent_id=l2.id, task=name, inputs=InputArtifactRefs(id=ident("inputs"), cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), parent_id=l2.id, refs=[]), tools=["read_artifact"], output_contract=OutputContract(id=ident("contract"), cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), parent_id=l2.id, required_files=["result.json", "analysis.md", "evidence.json", "manifest.json"]), assigned_role_id=role.id)
            self.store.write_json(f"cycles/{cycle.id}/l2/{l2.id}/tasks/{task.id}.json", task, artifact_id=task.id, cycle_id=cycle.id, creator=l2.id, parent_id=l2.id, lineage_refs=[role.id])
            out.append(task)
        return out

    def run_l3(self, cycle: Cycle, l2: AgentInstance, task: TaskSpec, worker_summary: str | None = None) -> list[ArtifactRef]:
        self._count_invocation()
        l3 = AgentInstance(id=ident("l3"), cycle_id=cycle.id, creator="l1-coordinator", created_at=utc_now(), parent_id=l2.id, level="L3", template="L3", task_spec_id=task.id)
        base = f"cycles/{cycle.id}/l3/{l3.id}"
        result = WorkerResult(id=ident("result"), cycle_id=cycle.id, creator=l3.id, created_at=utc_now(), parent_id=task.id, task_spec_id=task.id, status="PASS", summary=worker_summary or f"Completed harmless smoke task: {task.task}", evidence_refs=[], warnings=[])
        refs = [self.store.write_json(f"{base}/result.json", result, artifact_id=result.id, cycle_id=cycle.id, creator=l3.id, parent_id=task.id, lineage_refs=[task.id])]
        analysis = self.store.write_text(f"{base}/analysis.md", f"# L3 analysis\n\nTask: {task.task}\n\nStatus: PASS\n", artifact_id=ident("analysis"), cycle_id=cycle.id, creator=l3.id, parent_id=task.id, lineage_refs=[refs[0].id])
        evidence = self.store.write_json(f"{base}/evidence.json", {"schema_version": 1, "id": ident("evidence"), "cycle_id": cycle.id, "creator": l3.id, "created_at": utc_now(), "parent_id": task.id, "artifact_refs": [r.id for r in refs + [analysis]], "lineage_refs": [task.id], "evidence": "harmless local smoke input"}, artifact_id=ident("evidence-artifact"), cycle_id=cycle.id, creator=l3.id, parent_id=task.id, lineage_refs=[task.id])
        refs.append(analysis); refs.append(evidence)
        manifest = self.store.write_json(f"{base}/manifest.json", {"schema_version": 1, "id": ident("manifest"), "cycle_id": cycle.id, "creator": l3.id, "created_at": utc_now(), "parent_id": task.id, "artifact_refs": [r.id for r in refs], "lineage_refs": [task.id], "files": [r.path for r in refs]}, artifact_id=ident("manifest-artifact"), cycle_id=cycle.id, creator=l3.id, parent_id=task.id, lineage_refs=[r.id for r in refs])
        refs.append(manifest)
        return refs

    def write_l2_report(self, cycle: Cycle, l2: AgentInstance, role: RoleSpec, worker_refs: list[ArtifactRef], conclusion: str | None = None) -> list[ArtifactRef]:
        report = LeaderReport(id=ident("leader-report"), cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), parent_id=l2.id, role_spec_id=role.id, status="PASS", worker_result_refs=[r.id for r in worker_refs if r.kind == "json" and r.path.endswith("result.json")], conclusion=conclusion or f"Role {role.name} received {len(worker_refs)} leaf artifacts", warnings=[])
        refs = [self.store.write_json(f"cycles/{cycle.id}/l2/{l2.id}/leader_report.json", report, artifact_id=report.id, cycle_id=cycle.id, creator=l2.id, parent_id=l2.id, lineage_refs=[r.id for r in worker_refs])]
        refs.append(self.store.write_text(f"cycles/{cycle.id}/l2/{l2.id}/summary.md", f"# L2 summary\n\nRole: {role.name}\nArtifacts: {len(worker_refs)}\n", artifact_id=ident("l2-summary"), cycle_id=cycle.id, creator=l2.id, parent_id=report.id, lineage_refs=[report.id]))
        refs.append(self.store.write_json(f"cycles/{cycle.id}/l2/{l2.id}/evidence_refs.json", {"schema_version": 1, "id": ident("l2-evidence"), "cycle_id": cycle.id, "creator": l2.id, "created_at": utc_now(), "parent_id": report.id, "artifact_refs": [r.id for r in worker_refs], "lineage_refs": [r.id for r in worker_refs]}, artifact_id=ident("l2-evidence-artifact"), cycle_id=cycle.id, creator=l2.id, parent_id=report.id, lineage_refs=[r.id for r in worker_refs]))
        refs.append(self.store.write_json(f"cycles/{cycle.id}/l2/{l2.id}/manifest.json", {"schema_version": 1, "id": ident("l2-manifest"), "cycle_id": cycle.id, "creator": l2.id, "created_at": utc_now(), "parent_id": report.id, "artifact_refs": [r.id for r in refs], "lineage_refs": [report.id]}, artifact_id=ident("l2-manifest-artifact"), cycle_id=cycle.id, creator=l2.id, parent_id=report.id, lineage_refs=[report.id]))
        return refs

    def write_l1_outputs(self, cycle: Cycle, leader_refs: list[ArtifactRef], state_summary: str | None = None, open_questions: list[str] | None = None) -> list[ArtifactRef]:
        synthesis = L1Synthesis(id=ident("l1-synthesis"), cycle_id=cycle.id, creator="l1-synthesis", created_at=utc_now(), parent_id=cycle.id, status="PASS", leader_report_refs=[r.id for r in leader_refs if r.path.endswith("leader_report.json")], state_summary=state_summary or f"Received {len(leader_refs)} L2 artifacts", open_questions=open_questions or ["L0 must determine the next direction"], active_veto_refs=[])
        refs = [self.store.write_json(f"cycles/{cycle.id}/l1/state.json", synthesis, artifact_id=synthesis.id, cycle_id=cycle.id, creator=synthesis.creator, parent_id=cycle.id, lineage_refs=[r.id for r in leader_refs])]
        for rel, value in [("task_graph.json", {"schema_version": 1, "id": ident("task-graph"), "cycle_id": cycle.id, "creator": "l1-coordinator", "created_at": utc_now(), "parent_id": cycle.id, "artifact_refs": [r.id for r in leader_refs], "lineage_refs": [r.id for r in leader_refs]}), ("open_questions.json", {"schema_version": 1, "id": ident("open-questions"), "cycle_id": cycle.id, "creator": "l1-synthesis", "created_at": utc_now(), "parent_id": synthesis.id, "artifact_refs": [synthesis.id], "lineage_refs": [synthesis.id], "questions": synthesis.open_questions}), ("active_vetoes.json", {"schema_version": 1, "id": ident("active-vetoes"), "cycle_id": cycle.id, "creator": "l1-coordinator", "created_at": utc_now(), "parent_id": synthesis.id, "artifact_refs": [], "lineage_refs": [synthesis.id], "vetoes": []})]:
            refs.append(self.store.write_json(f"cycles/{cycle.id}/l1/{rel}", value, artifact_id=value["id"], cycle_id=cycle.id, creator=value["creator"], parent_id=value["parent_id"], lineage_refs=value["lineage_refs"]))
        refs.append(self.store.write_text(f"cycles/{cycle.id}/l1/cycle_summary.md", f"# L1 cycle summary\n\n{synthesis.state_summary}\n", artifact_id=ident("cycle-summary"), cycle_id=cycle.id, creator="l1-synthesis", parent_id=synthesis.id, lineage_refs=[synthesis.id]))
        refs.append(self.store.write_json(f"cycles/{cycle.id}/l1/manifest.json", {"schema_version": 1, "id": ident("l1-manifest"), "cycle_id": cycle.id, "creator": "l1-coordinator", "created_at": utc_now(), "parent_id": cycle.id, "artifact_refs": [r.id for r in refs], "lineage_refs": [r.id for r in refs]}, artifact_id=ident("l1-manifest-artifact"), cycle_id=cycle.id, creator="l1-coordinator", parent_id=cycle.id, lineage_refs=[r.id for r in refs]))
        return refs

    def _count_invocation(self) -> None:
        self.invocations += 1
        if self.invocations > int(self.limits["max_total_agent_invocations"]):
            raise RuntimeError("max_total_agent_invocations exceeded")
