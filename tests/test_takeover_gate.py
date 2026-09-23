import json
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from chia_work.actions import ActionKind, TypedAction
from chia_work.bridge.council_chia_bridge import BridgeValidationError, validate_request
from chia_work.council.artifacts import ArtifactError, ArtifactStore
from chia_work.council.governance import Governance, GovernanceError
from chia_work.council.schemas import (
    AgentInstance,
    CapabilityGrant,
    Cycle,
    DecisionRecord,
    ExecutionRequest,
    InputArtifactRefs,
    OutputContract,
    Proposal,
    TaskSpec,
    utc_now,
)
import chia_work.takeover_gate as takeover_gate_module
from chia_work.takeover_gate import (
    ActionDraft,
    GateRunner,
    LeafOutput,
    SynthesisOutput,
    exposed_typed_action_contract,
    safe_action_surface,
    validate_exposed_action,
)
from chia_work.safety import Decision, SafetyGate


def valid_payload():
    return {
        "execution_request": {
            "id": "er", "cycle_id": "c", "creator": "l0", "created_at": utc_now(),
            "decision_record_id": "d", "typed_action": {"schema_version": 1, "action_kind": "RUN_BENCHMARK", "target": "chia-local-smoke", "payload": {"command": "chia:identity", "payload": "preflight"}}, "requested_by": "l0", "capability_grant_id": "g",
        },
        "decision_record": {
            "id": "d", "cycle_id": "c", "creator": "l1", "created_at": utc_now(), "proposal_id": "p", "status": "APPROVED", "review_refs": [], "veto_refs": [], "rationale": "preflight", "immutable": True,
        },
        "capability_grant": {"capabilities": ["REQUEST_EXECUTION"]},
    }


def test_schema_and_exposed_surface():
    action = validate_exposed_action(ActionDraft(action_kind="RUN_BENCHMARK", target="chia-local-smoke", payload={"command": "chia:identity", "payload": "x"}))
    assert action.kind is ActionKind.RUN_BENCHMARK
    assert safe_action_surface()["exposed"] == {
        "action_kind": "RUN_BENCHMARK",
        "target": "chia-local-smoke",
        "payload_constraints": {"command": "chia:identity", "payload_max_length": 256, "no_system_mutation": True, "no_hardware": True},
    }


def test_exact_typed_action_contract_accepts_valid_action():
    action = validate_exposed_action(ActionDraft(
        action_kind="RUN_BENCHMARK",
        target="chia-local-smoke",
        payload={"command": "chia:identity", "payload": "bounded"},
    ))
    assert action.kind is ActionKind.RUN_BENCHMARK
    assert action.target == "chia-local-smoke"


def test_unknown_top_level_field_is_rejected():
    try:
        ActionDraft.model_validate({
            "action_kind": "RUN_BENCHMARK",
            "target": "chia-local-smoke",
            "payload": {"command": "chia:identity"},
            "no_hardware": True,
        })
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown top-level TypedAction field was accepted")


def test_unknown_payload_field_is_rejected():
    try:
        validate_exposed_action(ActionDraft(
            action_kind="RUN_BENCHMARK",
            target="chia-local-smoke",
            payload={"command": "chia:identity", "no_system_mutation": True},
        ))
    except ValueError as exc:
        assert "outside the exposed surface" in str(exc)
    else:
        raise AssertionError("unknown payload field was accepted")


def test_wrong_target_and_command_are_rejected():
    for target, command in [("other-target", "chia:identity"), ("chia-local-smoke", "other-command")]:
        try:
            validate_exposed_action(ActionDraft(action_kind="RUN_BENCHMARK", target=target, payload={"command": command}))
        except ValueError:
            pass
        else:
            raise AssertionError("invalid action surface value was accepted")


def test_unknown_fields_are_not_repaired_after_model_generation():
    source = (Path(__file__).parents[1] / "src" / "chia_work" / "takeover_gate.py").read_text()
    assert 'pop("no_hardware"' not in source
    assert 'pop("no_system_mutation"' not in source
    assert 'del typed_action["no_hardware"]' not in source
    try:
        validate_exposed_action(ActionDraft(action_kind="RUN_BENCHMARK", target="chia-local-smoke", payload={"command": "chia:identity", "no_hardware": True}))
    except ValueError:
        pass
    else:
        raise AssertionError("invalid generated action was normalized instead of rejected")


def test_artifact_immutability(tmp_path):
    store = ArtifactStore(tmp_path)
    store.write_text("x.txt", "x", artifact_id="x", cycle_id="c", creator="t")
    try:
        store.write_text("x.txt", "y", artifact_id="y", cycle_id="c", creator="t")
    except ArtifactError:
        pass
    else:
        raise AssertionError("locked artifact was overwritten")


def test_governance_commit_reveal_decision_and_veto(tmp_path):
    gov = Governance(ArtifactStore(tmp_path), "c")
    proposal = Proposal(id="p", cycle_id="c", creator="l0", created_at=utc_now(), title="p", payload={}, proposer_id="l0")
    a = gov.commit_review(proposal, "a", "APPROVE", "ok")
    b = gov.commit_review(proposal, "b", "APPROVE", "ok")
    assert not a.revealed and not b.revealed
    revealed = gov.reveal_all({"a", "b"})
    assert all(item.revealed for item in revealed)
    veto = gov.record_veto(proposal, "b", "boundary", True)
    decision = gov.decide(proposal, [a.id, b.id])
    assert decision.status == "REJECTED" and decision.veto_refs == [veto.id]
    try:
        gov.record_veto(proposal, "x", "override", False)
    except GovernanceError:
        pass
    else:
        raise AssertionError("unauthorized veto accepted")


def test_bridge_and_rejections():
    assert validate_request(valid_payload())["hardware_executed"] is False
    bad = valid_payload()
    bad["execution_request"]["typed_action"]["payload"]["command"] = "rm -rf /"
    try:
        validate_request(bad)
    except BridgeValidationError:
        pass
    else:
        raise AssertionError("shell command accepted")
    bad = valid_payload()
    bad["decision_record"]["veto_refs"] = ["v"]
    try:
        validate_request(bad)
    except BridgeValidationError:
        pass
    else:
        raise AssertionError("active veto accepted")


def test_no_real_execution_in_preflight():
    action = TypedAction(ActionKind.RUN_BENCHMARK, "chia-local-smoke", {"command": "chia:identity", "payload": "x"})
    assert SafetyGate().evaluate(action).decision == Decision.ALLOW


def _run_fake_no_execution(tmp_path, monkeypatch):
    created_templates = []
    calls = []

    class L0TemplateStub:
        def __init__(self, instance_id):
            self.instance_id = instance_id
            created_templates.append(self)

    class L2TemplateStub(L0TemplateStub):
        pass

    class L3TemplateStub(L0TemplateStub):
        pass

    class FakeADKJsonAgent:
        def __init__(self, template):
            self.template = template

    monkeypatch.setattr(takeover_gate_module, "L0Template", L0TemplateStub)
    monkeypatch.setattr(takeover_gate_module, "L2Template", L2TemplateStub)
    monkeypatch.setattr(takeover_gate_module, "L3Template", L3TemplateStub)
    monkeypatch.setattr(takeover_gate_module, "ADKJsonAgent", FakeADKJsonAgent)

    def fake_call(self, agent, prompt, output_type, trace):
        self.model_calls += 1
        calls.append((output_type, json.loads(prompt)))
        if output_type is takeover_gate_module.InitialDirectionOutput:
            return output_type(
                objective="organize harmless metadata checks",
                rationale="bounded deterministic test",
                roles=[
                    {"name": "role-a", "mission": "inspect A", "capabilities": [], "max_l3": 1},
                    {"name": "role-b", "mission": "inspect B", "capabilities": [], "max_l3": 1},
                ],
                decision="CONTINUE",
                next_direction="stop after governance",
            )
        if output_type is takeover_gate_module.TaskOutput:
            return output_type(tasks=[{"task": "read metadata", "rationale": "bounded"}])
        if output_type is takeover_gate_module.LeafOutput:
            return output_type(status="PASS", summary="leaf complete", analysis="metadata only", evidence={"ok": True})
        if output_type is takeover_gate_module.LeaderOutput:
            return output_type(status="PASS", conclusion="all leaf checks passed", warnings=[])
        if output_type is takeover_gate_module.SynthesisOutput:
            return output_type(state_summary="L1 aggregate", open_questions=["none"], observation_interpretation="No observation exists before proposal.")
        if output_type is takeover_gate_module.ProposalOutput:
            return output_type(title="no execution", rationale="no action is required", request_execution=False, typed_action=None)
        if output_type is takeover_gate_module.ReviewOutput:
            return output_type(verdict="APPROVE", rationale="safe", veto=False, veto_reason=None)
        raise AssertionError(f"unexpected fake output type: {output_type}")

    monkeypatch.setattr(GateRunner, "_call", fake_call)
    runner = GateRunner(tmp_path / "fake-no-execution", "deterministic test")
    return runner, runner.run(), created_templates, calls


def test_bounded_takeover_limits():
    assert takeover_gate_module.TAKEOVER_LIMITS["max_wall_time"] == 1800
    assert takeover_gate_module.TAKEOVER_LIMITS["max_model_calls"] == 20
    assert takeover_gate_module.TAKEOVER_LIMITS["max_wall_time"] < float("inf")
    assert takeover_gate_module.TAKEOVER_LIMITS["max_model_calls"] < float("inf")


def test_expected_full_chain_fits_configured_call_budget():
    expected = 1 + 3 + 3 + 3 + 1 + 1 + 4 + 1 + 1
    assert expected == 18
    assert takeover_gate_module.TAKEOVER_LIMITS["max_model_calls"] == 20
    assert takeover_gate_module.TAKEOVER_LIMITS["max_model_calls"] - expected == 2


def test_l1_preproposal_synthesis_and_proposal_state_grounding(tmp_path, monkeypatch):
    runner, result, _, calls = _run_fake_no_execution(tmp_path, monkeypatch)
    assert result["status"] == "STOP_NO_MODEL_EXECUTION_REQUEST"
    names = [output_type.__name__ for output_type, _ in calls]
    assert names.index("SynthesisOutput") < names.index("ProposalOutput")
    synthesis_payloads = [payload for output_type, payload in calls if output_type in (takeover_gate_module.LeaderOutput, takeover_gate_module.SynthesisOutput)]
    assert len(synthesis_payloads) == 3
    assert all("execution_grounding" in payload for payload in synthesis_payloads)
    assert all(payload["execution_grounding"]["snapshot"]["execution_boundary_entries"] == 0 for payload in synthesis_payloads)
    assert all(payload["execution_grounding"]["snapshot"]["execution_observation_present"] is False for payload in synthesis_payloads)
    assert all("does not authorize or deny actions" in payload["execution_grounding"]["instruction"] and "decide whether to propose/request an action" in payload["execution_grounding"]["instruction"] for payload in synthesis_payloads)
    proposal_input = next(payload for output_type, payload in calls if output_type is takeover_gate_module.ProposalOutput)
    assert proposal_input["l1_synthesis"]["state_summary"] == "L1 aggregate"
    assert proposal_input["l1_synthesis_artifact"]["path"].endswith("l1/pre-proposal-state.json")
    assert proposal_input["execution_state"] == {
        "execution_request_created": False,
        "execution_attempted": False,
        "execution_observation_present": False,
    }
    assert proposal_input["typed_action_contract"] == exposed_typed_action_contract()
    instruction = proposal_input["instruction"]
    assert "Return only fields defined by the TypedAction schema" in instruction
    assert "Unknown top-level or payload fields are invalid" in instruction
    assert "no_hardware" in instruction and "no_system_mutation" in instruction
    assert "Safety constraints are enforced externally" in instruction
    assert "Only describe execution as having occurred if an ExecutionObservation artifact is actually supplied." in instruction
    assert "At this proposal stage, no execution has occurred." in instruction
    assert "Do not invent execution results." in instruction


def test_takeover_leaf_uses_l3_template_and_stops_without_execution(tmp_path, monkeypatch):
    runner, result, templates, _ = _run_fake_no_execution(tmp_path, monkeypatch)

    assert result["status"] == "STOP_NO_MODEL_EXECUTION_REQUEST"
    leaf_templates = [item for item in templates if item.instance_id.startswith("l3-")]
    assert len(leaf_templates) == 2
    assert all(isinstance(item, takeover_gate_module.L3Template) for item in leaf_templates)
    assert not any(isinstance(item, takeover_gate_module.L2Template) for item in leaf_templates)
    assert not list((runner.root / "cycles").glob("*/execution/request.json"))


def test_l3_identity_propagates_to_all_leaf_artifacts(tmp_path):
    runner = GateRunner(tmp_path / "identity", "deterministic identity test")
    cycle = Cycle(id="cycle-fixed", cycle_id="cycle-fixed", creator="l1-coordinator", created_at=utc_now(), run_id="run-fixed", index=0, limits={})
    l2 = AgentInstance(id="l2-fixed", cycle_id=cycle.id, creator="l1-coordinator", created_at=utc_now(), parent_id="role-fixed", level="L2", template="L2", role_spec_id="role-fixed")
    task = TaskSpec(
        id="task-fixed",
        cycle_id=cycle.id,
        creator=l2.id,
        created_at=utc_now(),
        parent_id=l2.id,
        task="read metadata",
        inputs=InputArtifactRefs(id="inputs-fixed", cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), refs=[]),
        tools=["read_artifact"],
        output_contract=OutputContract(id="contract-fixed", cycle_id=cycle.id, creator=l2.id, created_at=utc_now(), required_files=["result.json", "analysis.md", "evidence.json", "manifest.json"]),
        assigned_role_id="role-fixed",
    )
    refs = runner._write_l3(cycle, l2, task, LeafOutput(status="PASS", summary="ok", analysis="metadata only", evidence={"ok": True}), l3_id="l3-fixed")

    base = runner.root / "cycles" / cycle.id / "l3" / "l3-fixed"
    assert json.loads((base / "agent.json").read_text())['id'] == "l3-fixed"
    assert json.loads((base / "result.json").read_text())['creator'] == "l3-fixed"
    assert json.loads((base / "evidence.json").read_text())['creator'] == "l3-fixed"
    assert json.loads((base / "manifest.json").read_text())['creator'] == "l3-fixed"
    assert {Path(ref.path).name: ref.creator for ref in refs} == {
        "result.json": "l3-fixed",
        "analysis.md": "l3-fixed",
        "evidence.json": "l3-fixed",
        "manifest.json": "l3-fixed",
    }


def test_real_execution_failure_remains_distinct(monkeypatch, tmp_path):
    runner = GateRunner(tmp_path / "execution-failure", "deterministic execution failure test")
    request = ExecutionRequest(
        id="execution-request-fixed",
        cycle_id="cycle-fixed",
        creator="l0",
        created_at=utc_now(),
        decision_record_id="decision-fixed",
        typed_action={"schema_version": 1, "action_kind": "RUN_BENCHMARK", "target": "chia-local-smoke", "payload": {"command": "chia:identity", "payload": "test"}},
        requested_by="l0",
        capability_grant_id="grant-fixed",
    )
    decision = DecisionRecord(id="decision-fixed", cycle_id="cycle-fixed", creator="l1", created_at=utc_now(), proposal_id="proposal-fixed", status="APPROVED", review_refs=[], rationale="approved", immutable=True)
    capability = CapabilityGrant(id="grant-fixed", cycle_id="cycle-fixed", creator="l1", created_at=utc_now(), subject_id="l0", capabilities=["REQUEST_EXECUTION"], granted_by="l1")

    monkeypatch.setattr(takeover_gate_module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="simulated CHIA failure", stdout=""))
    try:
        runner._execute_once(request, decision, capability)
    except RuntimeError as exc:
        assert "CHIA worker failed" in str(exc)
        assert "STOP_NO_MODEL_EXECUTION_REQUEST" not in str(exc)
    else:
        raise AssertionError("execution failure was not raised")


def test_patch_does_not_reference_historical_takeover():
    source = (Path(__file__).parents[1] / "src" / "chia_work" / "takeover_gate.py").read_text()
    assert "takeover-20260922T095400Z" not in source
