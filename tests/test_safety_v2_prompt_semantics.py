from __future__ import annotations

import pytest

from chia_work.actions import ActionKind
from chia_work.council import agents
from chia_work.safety import Decision
from chia_work.takeover_gate import (
    GateRunner,
    ActionDraft,
    exposed_typed_action_contract,
    safe_action_surface,
    validate_exposed_action,
)


def _l0_instruction(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(agents.AgentTemplate, "make_adk_agent", lambda self, output_schema=None: None)
    return agents.L0Template().instruction


def test_l0_may_propose_governed_execution_but_proposal_is_not_execution(monkeypatch):
    instruction = _l0_instruction(monkeypatch)
    assert "may propose or request a governed execution" in instruction
    assert "A proposal is not execution" in instruction
    assert "deterministic governed system may validate" in instruction


def test_l0_still_has_no_direct_execution_authority(monkeypatch):
    instruction = _l0_instruction(monkeypatch)
    for prohibited in (
        "Never directly execute CHIA",
        "executor",
        "shell command",
        "Ray execution",
        "hardware",
        "execution backend",
    ):
        assert prohibited in instruction
    assert "directly invoke CHIA" not in instruction


def test_action_surface_and_identity_command_remain_unchanged():
    surface = safe_action_surface()
    contract = exposed_typed_action_contract()
    assert surface["exposed"]["action_kind"] == "RUN_BENCHMARK"
    assert surface["exposed"]["target"] == "chia-local-smoke"
    assert surface["exposed"]["payload_constraints"]["command"] == "chia:identity"
    assert contract["fixed_values"]["payload.command"] == "chia:identity"
    action = validate_exposed_action(ActionDraft(
        action_kind="RUN_BENCHMARK",
        target="chia-local-smoke",
        payload={"command": "chia:identity"},
    ))
    assert action.kind == ActionKind.RUN_BENCHMARK
    assert action.target == "chia-local-smoke"
    assert action.params == {"command": "chia:identity"}


def test_unsupported_command_is_rejected_before_execution_request_or_executor(tmp_path, monkeypatch):
    from test_observability import _fake_call, _install_model_stubs
    import chia_work.takeover_gate as takeover_gate

    _install_model_stubs(monkeypatch)
    runner = GateRunner(tmp_path / "run", "synthetic deterministic engineering probe")
    runner._call = _fake_call("bad_action").__get__(runner, GateRunner)
    sentinel = {"executor_calls": 0}

    def forbidden_subprocess(*args, **kwargs):
        sentinel["executor_calls"] += 1
        raise AssertionError("CHIA subprocess boundary must not be reached")

    monkeypatch.setattr(takeover_gate.subprocess, "run", forbidden_subprocess)
    with pytest.raises(ValueError, match="only the typed chia:identity operation is exposed"):
        runner.run()
    import json
    terminal = json.loads((tmp_path / "run/lifecycle/terminal.json").read_text())
    counters = json.loads((tmp_path / "run/lifecycle/execution-counters.json").read_text())
    assert terminal["terminal_status"] == "REJECTED"
    assert terminal["terminal_phase"] == "ACTION_VALIDATION"
    assert terminal["execution_boundary_entered"] is False
    assert counters["execution_requests_created"] == 0
    assert counters["execution_boundary_entries"] == 0
    assert sentinel["executor_calls"] == 0


def test_known_unknown_target_safetygate_behavior_remains_allow():
    from chia_work.safety import SafetyGate
    from chia_work.actions import TypedAction

    result = SafetyGate().evaluate(TypedAction(ActionKind.RUN_BENCHMARK, "unrecognized-target", {"command": "chia:identity"}))
    assert result.decision == Decision.ALLOW


def test_non_veto_review_reject_behavior_remains_unchanged(tmp_path):
    from chia_work.council.artifacts import ArtifactStore
    from chia_work.council.governance import Governance
    from chia_work.council.schemas import Proposal, utc_now

    store = ArtifactStore(tmp_path)
    governance = Governance(store, "cycle-v2")
    proposal = Proposal(
        id="proposal-v2", cycle_id="cycle-v2", creator="l0", created_at=utc_now(),
        parent_id="direction-v2", title="synthetic policy-preservation probe",
        payload={"request_execution": True}, proposer_id="l0",
    )
    review = governance.commit_review(proposal, "reviewer-v2", "REJECT", "synthetic reject")
    governance.reveal_all({"reviewer-v2"})
    decision = governance.decide(proposal, [review.id])
    assert decision.status == "APPROVED"
