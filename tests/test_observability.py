import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from chia_work.actions import ActionKind, TypedAction
from chia_work.bridge import takeover_executor
from chia_work.bridge.council_chia_bridge import BridgeValidationError
from chia_work.council.artifacts import ArtifactStore
from chia_work.council.schemas import DecisionRecord, ExecutionRequest, utc_now
from chia_work.observability import ExecutionLifecycle, LifecycleIntegrityError
from chia_work.safety import Decision, SafetyGate
import chia_work.takeover_gate as tg
from chia_work.runner import run_action


class TemplateStub:
    def __init__(self, instance_id):
        self.instance_id = instance_id


class AgentStub:
    def __init__(self, template):
        self.template = template


def _install_model_stubs(monkeypatch):
    for name in ("ADKJsonAgent", "L0Template", "L1SynthesisTemplate", "L2Template", "L3Template"):
        monkeypatch.setattr(tg, name, AgentStub if name == "ADKJsonAgent" else TemplateStub)


def _fake_call(mode):
    def call(self, agent, prompt, output_type, trace):
        data = json.loads(prompt)
        if output_type is tg.InitialDirectionOutput:
            return output_type(objective="synthetic", rationale="test", roles=[
                {"name": "role-a", "mission": "metadata", "capabilities": [], "max_l3": 1},
                {"name": "role-b", "mission": "metadata", "capabilities": [], "max_l3": 1},
            ], decision="CONTINUE", next_direction="stop")
        if output_type is tg.TaskOutput:
            return output_type(tasks=[{"task": "metadata", "rationale": "test"}])
        if output_type is tg.LeafOutput:
            return output_type(status="PASS", summary="metadata", analysis="test", evidence={"synthetic": True})
        if output_type is tg.LeaderOutput:
            return output_type(status="PASS", conclusion="test", warnings=[])
        if output_type is tg.SynthesisOutput:
            return output_type(state_summary="test", open_questions=[], observation_interpretation="test")
        if output_type is tg.NextDirectionOutput:
            return output_type(objective="stop", next_direction="stop", requested_roles=[], rationale="test")
        if output_type is tg.ProposalOutput:
            request = mode in {"veto", "bad_action", "valid_action", "capability_error"}
            command = "not-a-chia-operation" if mode == "bad_action" else "chia:identity"
            return output_type(title="synthetic", rationale="test", request_execution=request,
                typed_action=(tg.ActionDraft(action_kind="RUN_BENCHMARK", target="chia-local-smoke",
                    payload={"command": command, "payload": "test"}) if request else None))
        if output_type is tg.ReviewOutput:
            veto = mode == "veto" and data.get("review_function") == "safety"
            verdict = "REJECT" if mode == "review_reject" else "APPROVE"
            return output_type(verdict=verdict, rationale="synthetic review", veto=veto,
                veto_reason="synthetic veto" if veto else None)
        raise AssertionError(output_type)
    return call


def _run_gate(tmp_path, monkeypatch, mode):
    _install_model_stubs(monkeypatch)
    runner = tg.GateRunner(tmp_path / "run", "synthetic engineering probe")
    runner._call = _fake_call(mode).__get__(runner, tg.GateRunner)
    return runner, runner.run()


def _artifact_json(root, rel):
    return json.loads((root / rel).read_text())


def test_gate_veto_has_terminal_artifact_and_zero_boundary(tmp_path, monkeypatch):
    runner, result = _run_gate(tmp_path, monkeypatch, "veto")
    root = tmp_path / "run"
    assert result["status"] == "TAKEOVER_REJECTED_BY_GEMINI_VETO"
    terminal = _artifact_json(root, "lifecycle/terminal.json")
    counters = _artifact_json(root, "lifecycle/execution-counters.json")
    assert terminal["terminal_status"] == "REJECTED"
    assert terminal["terminal_phase"] == "GOVERNANCE"
    assert terminal["execution_boundary_entered"] is False
    assert counters["execution_boundary_entries"] == 0
    assert counters["execution_requests_created"] == 0
    assert all(runner.store.verify(r) for r in runner.store.all_refs())


def test_no_request_status_preserved_and_terminal_is_durable(tmp_path, monkeypatch):
    runner, result = _run_gate(tmp_path, monkeypatch, "no_request")
    root = tmp_path / "run"
    assert result["status"] == "STOP_NO_MODEL_EXECUTION_REQUEST"
    terminal = _artifact_json(root, "lifecycle/terminal.json")
    assert terminal["terminal_status"] == "STOPPED"
    assert terminal["terminal_phase"] == "PROPOSAL"
    assert terminal["execution_boundary_entered"] is False
    assert _artifact_json(root, "lifecycle/execution-counters.json")["execution_boundary_entries"] == 0


def test_action_surface_rejection_has_terminal_and_no_request(tmp_path, monkeypatch):
    _install_model_stubs(monkeypatch)
    runner = tg.GateRunner(tmp_path / "run", "synthetic engineering probe")
    runner._call = _fake_call("bad_action").__get__(runner, tg.GateRunner)
    with pytest.raises(ValueError):
        runner.run()
    terminal = _artifact_json(tmp_path / "run", "lifecycle/terminal.json")
    counts = _artifact_json(tmp_path / "run", "lifecycle/execution-counters.json")
    assert terminal["terminal_status"] == "REJECTED"
    assert terminal["terminal_phase"] == "ACTION_VALIDATION"
    assert terminal["references"]["proposal_id"]
    assert counts["execution_requests_created"] == 0
    assert counts["execution_boundary_entries"] == 0


def test_capability_validation_failure_keeps_rejection_pre_boundary(tmp_path, monkeypatch):
    _install_model_stubs(monkeypatch)
    monkeypatch.setattr(tg, "validate_request", lambda payload: (_ for _ in ()).throw(BridgeValidationError("REQUEST_EXECUTION capability is not granted")))
    runner = tg.GateRunner(tmp_path / "run", "synthetic engineering probe")
    runner._call = _fake_call("capability_error").__get__(runner, tg.GateRunner)
    with pytest.raises(BridgeValidationError):
        runner.run()
    terminal = _artifact_json(tmp_path / "run", "lifecycle/terminal.json")
    counts = _artifact_json(tmp_path / "run", "lifecycle/execution-counters.json")
    assert terminal["terminal_status"] == "REJECTED"
    assert terminal["terminal_phase"] == "EXECUTION_DISPATCH"
    assert counts["execution_requests_created"] == 1
    assert counts["execution_boundary_entries"] == 0


def test_direct_child_safety_gate_deny_records_terminal_without_boundary(tmp_path, monkeypatch):
    run_id = "child-denial"
    stream = tmp_path / ".events.jsonl"
    monkeypatch.setenv("SAFEAGENT_LIFECYCLE_PATH", str(stream))
    monkeypatch.setenv("SAFEAGENT_RUN_ID", run_id)
    request = ExecutionRequest(id="er", cycle_id="c", creator="l0", created_at=utc_now(), decision_record_id="d",
        typed_action={"schema_version": 1, "action_kind": "RUN_BENCHMARK", "target": "chia-local-smoke", "payload": {"command": "chia:not-identity"}},
        requested_by="l0", capability_grant_id="g")
    decision = DecisionRecord(id="d", cycle_id="c", creator="l1", created_at=utc_now(), proposal_id="p", status="APPROVED", review_refs=[], veto_refs=[], rationale="test", immutable=True)
    payload = {"execution_request": request.model_dump(mode="json"), "decision_record": decision.model_dump(mode="json"), "capability_grant": {"capabilities": ["REQUEST_EXECUTION"]}}
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr("sys.stdout", stdout)
    with patch.object(takeover_executor, "execute_real_action", side_effect=AssertionError("executor reached")):
        assert takeover_executor.main() == 0
    result = json.loads(stdout.getvalue())
    assert result["status"] == "REJECTED" and result["safety_decision"] == "DENY"
    lifecycle = ExecutionLifecycle(run_id, stream)
    assert lifecycle.counters()["execution_boundary_entries"] == 0
    assert lifecycle.terminal_event()["terminal_phase"] == "SAFETY_GATE"
    refs = lifecycle.persist(ArtifactStore(tmp_path / "store"))
    assert all(ArtifactStore(tmp_path / "store").verify(r) for r in refs)


def test_mocked_allowed_boundary_and_failure_counters_are_exact(tmp_path):
    for suffix, ending, expected in (("ok", "execution_completed", (1, 1, 0)), ("failed", "execution_failed", (1, 0, 1))):
        lifecycle = ExecutionLifecycle(suffix, tmp_path / suffix / ".events.jsonl")
        lifecycle.append("execution_request_created", phase="REQUEST", status="REQUESTED", request_id="r")
        lifecycle.append("execution_boundary_entered", phase="EXECUTOR", status="ENTERED", request_id="r")
        lifecycle.append(ending, phase="EXECUTOR", status=ending.upper(), request_id="r")
        lifecycle.terminal("COMPLETED" if suffix == "ok" else "EXECUTION_FAILED", "EXECUTOR", "synthetic")
        counts = lifecycle.counters()
        assert (counts["execution_boundary_entries"], counts["execution_completions"], counts["execution_failures"]) == expected
        refs = lifecycle.persist(ArtifactStore(tmp_path / f"store-{suffix}"))
        assert all(ArtifactStore(tmp_path / f"store-{suffix}").verify(r) for r in refs)


def test_unknown_target_remains_allowed_and_reject_vote_without_veto_is_approved(tmp_path, monkeypatch):
    action = TypedAction(ActionKind.RUN_BENCHMARK, "unsupported-target", {"command": "chia:unknown.operation"})
    assert SafetyGate().evaluate(action).decision is Decision.ALLOW
    runner, result = _run_gate(tmp_path, monkeypatch, "review_reject")
    assert result["status"] == "STOP_NO_MODEL_EXECUTION_REQUEST"
    decision = next((tmp_path / "run").glob("cycles/*/decisions/*.json"))
    assert json.loads(decision.read_text())["status"] == "APPROVED"


def test_generic_run_record_has_explicit_counter_and_intervention_fields():
    class MockExecutor:
        mocked = True
        def execute(self, action):
            return {"backend": "mock", "status": "success", "exit_code": 0, "verified": True}
    action = TypedAction(ActionKind.BUILD, "demo", {"command": "build"})
    result = run_action(action, variant="S2", task_id="counter-test", safety_enabled=True, executor=MockExecutor()).record
    assert result["execution_counters"] == {
        "execution_requests_created": 0, "execution_boundary_entries": 0,
        "execution_completions": 0, "execution_failures": 0,
    }
    assert result["intervention_snapshot"]["manual_gemini_output_repair_count"] == 0


def test_hash_chain_detects_tamper_and_terminal_is_append_only(tmp_path):
    stream = tmp_path / "events.jsonl"
    lifecycle = ExecutionLifecycle("run", stream)
    lifecycle.append("run_started", phase="INITIALIZATION", status="STARTED")
    lifecycle.terminal("STOPPED", "PROPOSAL", "no request")
    with pytest.raises(LifecycleIntegrityError):
        lifecycle.append("late", phase="OTHER", status="BAD")
    lines = stream.read_text().splitlines()
    damaged = json.loads(lines[0]); damaged["status"] = "ALTERED"
    lines[0] = json.dumps(damaged)
    stream.write_text("\n".join(lines) + "\n")
    with pytest.raises(LifecycleIntegrityError):
        lifecycle.events()


def _install_fake_chia(monkeypatch, *, fail=False):
    import sys
    import types
    ray = types.ModuleType("ray")
    ray.is_initialized = lambda: True
    chia = types.ModuleType("chia")
    chia.__path__ = []
    base = types.ModuleType("chia.base")
    base.__path__ = []
    module = types.ModuleType("chia.base.ChiaFunction")
    class Remote:
        def __init__(self, fn): self.fn = fn
        def chia_remote(self, payload):
            return lambda: self.fn(payload)
    class ChiaFunction:
        def __call__(self, fn): return Remote(fn)
    module.ChiaFunction = ChiaFunction
    def fake_get(callable_):
        if fail: raise RuntimeError("synthetic backend fault")
        return callable_()
    module.get = fake_get
    for name, value in (("ray", ray), ("chia", chia), ("chia.base", base), ("chia.base.ChiaFunction", module)):
        monkeypatch.setitem(sys.modules, name, value)


def test_chia_adapter_records_boundary_immediately_before_mocked_remote_call(tmp_path, monkeypatch):
    from chia_work.chia_adapter import ChiaLocalExecutor
    stream = tmp_path / "events.jsonl"
    monkeypatch.setenv("SAFEAGENT_LIFECYCLE_PATH", str(stream))
    monkeypatch.setenv("SAFEAGENT_RUN_ID", "adapter-ok")
    monkeypatch.setenv("SAFEAGENT_EXECUTION_REQUEST_ID", "request-1")
    _install_fake_chia(monkeypatch)
    action = TypedAction(ActionKind.RUN_BENCHMARK, "chia-local-smoke", {"command": "chia:identity"})
    result = ChiaLocalExecutor().execute(action)
    lifecycle = ExecutionLifecycle("adapter-ok", stream)
    assert result["verified"] and result["execution_boundary_entered"] is True
    assert lifecycle.counters() == {
        "execution_requests_created": 0,
        "execution_boundary_entries": 1,
        "execution_completions": 1,
        "execution_failures": 0,
    }
    events = lifecycle.events()
    assert [e["event_type"] for e in events] == ["execution_boundary_entered", "execution_completed"]
    assert events[0]["execution_request_id"] == "request-1"


def test_chia_adapter_records_failure_after_boundary_entry(tmp_path, monkeypatch):
    from chia_work.chia_adapter import ChiaLocalExecutor
    stream = tmp_path / "events.jsonl"
    monkeypatch.setenv("SAFEAGENT_LIFECYCLE_PATH", str(stream))
    monkeypatch.setenv("SAFEAGENT_RUN_ID", "adapter-fail")
    _install_fake_chia(monkeypatch, fail=True)
    action = TypedAction(ActionKind.RUN_BENCHMARK, "chia-local-smoke", {"command": "chia:identity"})
    with pytest.raises(RuntimeError, match="synthetic backend fault"):
        ChiaLocalExecutor().execute(action)
    counts = ExecutionLifecycle("adapter-fail", stream).counters()
    assert counts["execution_boundary_entries"] == 1
    assert counts["execution_failures"] == 1
    assert counts["execution_completions"] == 0


def _run_gate_with_mock_child(tmp_path, monkeypatch, *, fail_after_boundary=False, verification_failure=False):
    import os
    import sys
    _install_model_stubs(monkeypatch)
    runner = tg.GateRunner(tmp_path / "run", "synthetic engineering integration")
    runner._call = _fake_call("valid_action").__get__(runner, tg.GateRunner)
    def fake_subprocess(args, *, input, text, capture_output, timeout, env, check):
        stream = env["SAFEAGENT_LIFECYCLE_PATH"]
        run_id = env["SAFEAGENT_RUN_ID"]
        request_id = env["SAFEAGENT_EXECUTION_REQUEST_ID"]
        def fake_execute(action):
            lifecycle = ExecutionLifecycle.from_environment()
            boundary = lifecycle.append("execution_boundary_entered", phase="CHIA_EXECUTOR", status="ENTERED", execution_request_id=request_id)
            if fail_after_boundary:
                lifecycle.append("execution_failed", phase="CHIA_EXECUTOR", status="FAILED", execution_request_id=request_id, boundary_event_id=boundary["event_id"], error_type="RuntimeError")
                raise RuntimeError("synthetic backend fault")
            if verification_failure:
                lifecycle.append("execution_failed", phase="VERIFIER", status="FAILED", execution_request_id=request_id, boundary_event_id=boundary["event_id"], error_type="VerificationMismatch")
                return {"backend": "mock-chia", "status": "success", "exit_code": 0, "verified": False}
            lifecycle.append("execution_completed", phase="CHIA_EXECUTOR", status="COMPLETED", execution_request_id=request_id, boundary_event_id=boundary["event_id"])
            return {"backend": "mock-chia", "status": "success", "exit_code": 0, "verified": True}
        stdout = io.StringIO()
        with patch.dict(os.environ, env), patch.object(sys, "stdin", io.StringIO(input)), patch.object(sys, "stdout", stdout), patch.object(takeover_executor, "execute_real_action", side_effect=fake_execute):
            rc = takeover_executor.main()
        return SimpleNamespace(returncode=rc, stdout=stdout.getvalue(), stderr="")
    monkeypatch.setattr(tg.subprocess, "run", fake_subprocess)
    try:
        result = runner.run()
        return runner, result
    except Exception as exc:
        return runner, exc


def test_gate_valid_mock_execution_has_one_durable_boundary_entry(tmp_path, monkeypatch):
    runner, result = _run_gate_with_mock_child(tmp_path, monkeypatch)
    root = tmp_path / "run"
    assert result["status"] == "TAKEOVER_GATE_PASS"
    assert result["execution_counters"] == {
        "execution_requests_created": 1,
        "execution_boundary_entries": 1,
        "execution_completions": 1,
        "execution_failures": 0,
    }
    validation = __import__("chia_work.observability", fromlist=["validate_lifecycle_artifacts"]).validate_lifecycle_artifacts(root, root.name)
    assert validation["valid"] and validation["counters"]["execution_boundary_entries"] == 1
    assert _artifact_json(root, "lifecycle/terminal.json")["terminal_status"] == "COMPLETED"


def test_gate_mock_backend_failure_after_entry_is_not_preexecution_rejection(tmp_path, monkeypatch):
    runner, result = _run_gate_with_mock_child(tmp_path, monkeypatch, fail_after_boundary=True)
    root = tmp_path / "run"
    assert isinstance(result, RuntimeError)
    terminal = _artifact_json(root, "lifecycle/terminal.json")
    counts = _artifact_json(root, "lifecycle/execution-counters.json")
    assert terminal["terminal_status"] == "EXECUTION_FAILED"
    assert terminal["execution_boundary_entered"] is True
    assert counts["execution_boundary_entries"] == 1
    assert counts["execution_failures"] == 1
    assert counts["execution_completions"] == 0


def test_lifecycle_artifact_validator_detects_required_corruption_classes(tmp_path):
    import hashlib
    import shutil
    from chia_work.observability import validate_lifecycle_artifacts

    source = tmp_path / "source"
    source.mkdir()
    source_run = "validation-run"
    lifecycle = ExecutionLifecycle(source_run, source / ".stream")
    lifecycle.append("run_started", phase="INIT", status="STARTED")
    lifecycle.append("execution_request_created", phase="REQUEST", status="REQUESTED", request_id="req")
    lifecycle.append("execution_boundary_entered", phase="EXECUTOR", status="ENTERED", request_id="req")
    lifecycle.terminal("COMPLETED", "EXECUTOR", "done")
    store = ArtifactStore(source)
    lifecycle.persist(store)
    assert validate_lifecycle_artifacts(source, source_run)["valid"]

    def rechain(records):
        previous = None
        for item in records:
            item.pop("event_sha256", None)
            item["previous_event_sha256"] = previous
            data = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            item["event_sha256"] = __import__("hashlib").sha256(data).hexdigest()
            previous = item["event_sha256"]
        return records

    def fix_index(root, relpath):
        path = root / "ledger" / "artifact-index.jsonl"
        refs = [json.loads(line) for line in path.read_text().splitlines()]
        digest = hashlib.sha256((root / relpath).read_bytes()).hexdigest()
        for ref in refs:
            if ref["path"] == relpath: ref["sha256"] = digest
        path.write_text("".join(json.dumps(ref, sort_keys=True, separators=(",", ":")) + "\n" for ref in refs))

    mutations = {
        "missing_field": lambda r, ev: (ev[1].pop("phase"), rechain(ev)),
        "malformed_json": lambda r, ev: (r.joinpath("lifecycle/events.jsonl").write_text("{bad json\n"), None),
        "truncated_jsonl": lambda r, ev: (r.joinpath("lifecycle/events.jsonl").write_text("\n".join(r.joinpath("lifecycle/events.jsonl").read_text().splitlines()[:-1]) + "\n{truncated"), None),
        "duplicate_event_id": lambda r, ev: (ev[1].update(event_id=ev[0]["event_id"]), rechain(ev)),
        "out_of_order_sequence": lambda r, ev: (ev.__setitem__(slice(1, 3), reversed(ev[1:3])), None),
        "incorrect_run_association": lambda r, ev: (ev[1].update(run_id="other-run"), rechain(ev)),
    }
    detected = 0
    for name, mutate in mutations.items():
        target = tmp_path / name
        shutil.copytree(source, target)
        event_file = target / "lifecycle/events.jsonl"
        events = [json.loads(line) for line in event_file.read_text().splitlines()]
        mutate(target, events)
        if name not in {"malformed_json", "truncated_jsonl"}:
            event_file.write_text("".join(json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for item in events))
        fix_index(target, "lifecycle/events.jsonl")
        try:
            validate_lifecycle_artifacts(target, source_run)
        except Exception:
            detected += 1
        else:
            raise AssertionError(f"corruption was not detected: {name}")

    for name, relpath, mutate_file in (
        ("invalid_counter", "lifecycle/execution-counters.json", lambda d: d.update(execution_boundary_entries=99)),
        ("hash_mismatch", "lifecycle/intervention-snapshot.json", lambda d: d.update(not_measured_claim=False)),
    ):
        target = tmp_path / name
        shutil.copytree(source, target)
        path = target / relpath
        if name == "invalid_counter":
            data = json.loads(path.read_text()); mutate_file(data); path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
            fix_index(target, relpath)
        else:
            data = json.loads(path.read_text()); mutate_file(data); path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        try:
            validate_lifecycle_artifacts(target, source_run)
        except Exception:
            detected += 1
        else:
            raise AssertionError(f"corruption was not detected: {name}")
    assert detected == 8


def test_lifecycle_artifact_write_failure_preserves_gate_status(tmp_path, monkeypatch):
    _install_model_stubs(monkeypatch)
    runner = tg.GateRunner(tmp_path / "run", "synthetic engineering probe")
    runner._call = _fake_call("no_request").__get__(runner, tg.GateRunner)
    original_write_text = runner.store.write_text
    def fail_lifecycle_write(relpath, *args, **kwargs):
        if relpath == "lifecycle/events.jsonl":
            raise OSError("synthetic artifact disk fault")
        return original_write_text(relpath, *args, **kwargs)
    monkeypatch.setattr(runner.store, "write_text", fail_lifecycle_write)
    result = runner.run()
    assert result["status"] == "STOP_NO_MODEL_EXECUTION_REQUEST"
    assert "synthetic artifact disk fault" in result["lifecycle_persistence_error"]
    lifecycle = ExecutionLifecycle("run", tmp_path / "run" / ".lifecycle-events.jsonl")
    assert lifecycle.terminal_event()["terminal_status"] == "STOPPED"
    assert lifecycle.counters()["execution_boundary_entries"] == 0


def test_gate_verification_failure_is_post_execution_and_distinct(tmp_path, monkeypatch):
    runner, result = _run_gate_with_mock_child(tmp_path, monkeypatch, verification_failure=True)
    root = tmp_path / "run"
    assert isinstance(result, RuntimeError)
    terminal = _artifact_json(root, "lifecycle/terminal.json")
    counts = _artifact_json(root, "lifecycle/execution-counters.json")
    assert terminal["terminal_status"] == "VERIFICATION_FAILED"
    assert terminal["terminal_phase"] == "VERIFIER"
    assert terminal["execution_boundary_entered"] is True
    assert counts["execution_boundary_entries"] == 1
    assert counts["execution_failures"] == 1
    assert counts["execution_completions"] == 0


def test_boundary_event_storage_failure_does_not_change_allowed_execution(tmp_path, monkeypatch):
    from chia_work.chia_adapter import ChiaLocalExecutor
    stream = tmp_path / "events.jsonl"
    monkeypatch.setenv("SAFEAGENT_LIFECYCLE_PATH", str(stream))
    monkeypatch.setenv("SAFEAGENT_RUN_ID", "adapter-observe-fault")
    _install_fake_chia(monkeypatch)
    monkeypatch.setattr(ExecutionLifecycle, "append", lambda *a, **k: (_ for _ in ()).throw(OSError("synthetic lifecycle disk fault")))
    action = TypedAction(ActionKind.RUN_BENCHMARK, "chia-local-smoke", {"command": "chia:identity"})
    result = ChiaLocalExecutor().execute(action)
    assert result["status"] == "success" and result["verified"]
    assert result["execution_boundary_entered"] is True
    assert result["execution_lifecycle_errors"]


def test_boundary_exception_attribute_keeps_generic_counter_truthful(monkeypatch):
    class BoundaryFailure(RuntimeError):
        execution_boundary_entered = True
        execution_boundary_event_id = "evt-1"
    class FailingRealExecutor:
        mocked = False
        def execute(self, action): raise BoundaryFailure("after boundary")
    result = run_action(
        TypedAction(ActionKind.BUILD, "demo", {"command": "build"}),
        variant="S2", task_id="boundary-fail", safety_enabled=True,
        executor=FailingRealExecutor(),
    ).record
    assert result["execution_counters"]["execution_boundary_entries"] == 1
    assert result["execution_counters"]["execution_failures"] == 1
    assert result["tool_result"]["execution_boundary_event_id"] == "evt-1"


def test_lifecycle_append_failure_preserves_preexisting_gate_status(tmp_path, monkeypatch):
    _install_model_stubs(monkeypatch)
    runner = tg.GateRunner(tmp_path / "run", "synthetic engineering probe")
    runner._call = _fake_call("no_request").__get__(runner, tg.GateRunner)
    monkeypatch.setattr(runner.lifecycle, "append", lambda *a, **k: (_ for _ in ()).throw(OSError("synthetic append fault")))
    result = runner.run()
    assert result["status"] == "STOP_NO_MODEL_EXECUTION_REQUEST"
    assert result["execution_counters"]["execution_boundary_entries"] == 0
    assert result["lifecycle_observability_errors"]
    assert "synthetic append fault" in result["lifecycle_persistence_error"]


def test_agentic_loop_attempt_history_keeps_per_attempt_observability():
    from chia_work.agentic_loop import run_agentic_task

    class MockExecutor:
        mocked = True
        def execute(self, action):
            return {"backend": "mock", "status": "success", "exit_code": 0, "verified": True}

    result = run_agentic_task(
        "synthetic task", variant="S2", task_id="attempt-counter-test",
        executor=MockExecutor(),
        initial_action=TypedAction(ActionKind.BUILD, "demo", {"command": "build"}),
    )
    attempt = result.attempts[0]
    final_record = result.final.record
    assert attempt["run_id"] == final_record["run_id"]
    assert attempt["execution_counters"] == final_record["execution_counters"]
    assert attempt["intervention_snapshot"] == final_record["intervention_snapshot"]
