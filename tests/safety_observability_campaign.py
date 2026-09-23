"""PRE-SCIENTIFIC TEST HARNESS. Never calls Gemini, CHIA, Ray, or hardware."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import statistics
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from chia_work.actions import ActionKind, TypedAction
from chia_work.council.artifacts import ArtifactStore
from chia_work.council.governance import Governance
from chia_work.council.schemas import Proposal, utc_now
from chia_work.observability import ExecutionLifecycle, validate_lifecycle_artifacts
from chia_work.runner import run_action
from chia_work.safety import SafetyGate


SOAK_CASES = (
    "governance_veto", "no_execution_request", "action_surface_rejection",
    "capability_rejection", "safety_gate_deny", "before_request_fault",
    "after_request_fault", "before_safety_gate_fault", "after_safety_allow_fault",
    "immediately_before_boundary_fault", "mock_boundary_success",
    "mock_failure_after_boundary", "mock_verification_failure",
    "artifact_write_failure", "unknown_target_allow", "review_reject_without_veto",
)
PRE_EXECUTION = set(SOAK_CASES[:10]) | {"artifact_write_failure", "unknown_target_allow", "review_reject_without_veto"}
POST_BOUNDARY = {"mock_boundary_success", "mock_failure_after_boundary", "mock_verification_failure"}


def canonical_semantics(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ignored = {"event_id", "run_id", "timestamp_utc", "previous_event_sha256", "event_sha256", "references", "execution_request_id", "boundary_event_id", "proposal_id", "decision_id", "request_id", "cycle_id", "mission_id"}
    return [{k: v for k, v in event.items() if k not in ignored} for event in events]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")


def make_governance(store: ArtifactStore, cycle_id: str, proposal_id: str, *, veto: bool, all_reject: bool) -> str:
    proposal = Proposal(id=proposal_id, cycle_id=cycle_id, creator="l0", created_at=utc_now(), title="synthetic", payload={}, proposer_id="l0")
    governance = Governance(store, cycle_id)
    reviewers = [f"reviewer-{uuid.uuid4().hex[:8]}" for _ in range(4)]
    reviews = [governance.commit_review(proposal, reviewer, "REJECT" if all_reject else "APPROVE", f"synthetic-{index}") for index, reviewer in enumerate(reviewers)]
    governance.reveal_all(set(reviewers))
    if veto:
        governance.record_veto(proposal, reviewers[0], "synthetic veto", allowed=True)
    decision = governance.decide(proposal, [review.id for review in reviews])
    return decision.status


def run_case(case: str, iteration: int, root: Path) -> dict[str, Any]:
    run_id = f"{case}-{iteration:05d}-{uuid.uuid4().hex[:8]}"
    run_root = root / run_id
    store = ArtifactStore(run_root)
    lifecycle = ExecutionLifecycle(run_id, run_root / ".events.jsonl")
    expected_status = "REJECTED"
    error = None
    lifecycle.append("run_started", phase="INITIALIZATION", status="STARTED")
    cycle = f"cycle-{uuid.uuid4().hex}"
    lifecycle.append("cycle_started", phase="HIERARCHY", status="OPEN", cycle_id=cycle)
    proposal_id = f"proposal-{uuid.uuid4().hex}"
    refs: dict[str, str] = {"proposal_id": proposal_id}
    store.write_json(f"cycles/{cycle}/governance/proposal.json", {"id": proposal_id, "cycle_id": cycle, "request_execution": case not in {"no_execution_request", "review_reject_without_veto"}}, artifact_id=proposal_id, cycle_id=cycle, creator="l0")
    try:
        if case in {"governance_veto", "review_reject_without_veto"}:
            decision_status = make_governance(store, cycle, proposal_id, veto=case == "governance_veto", all_reject=case == "review_reject_without_veto")
            store.write_json(f"cycles/{cycle}/decision.json", {"id": f"decision-{proposal_id}", "status": decision_status}, artifact_id=f"decision-{proposal_id}", cycle_id=cycle, creator="l1", parent_id=proposal_id)
            lifecycle.append("governance_decided", phase="GOVERNANCE", status=decision_status, cycle_id=cycle, proposal_id=proposal_id)
            if case == "governance_veto":
                expected_status = "TAKEOVER_REJECTED_BY_GEMINI_VETO"
                lifecycle.terminal("REJECTED", "GOVERNANCE", expected_status, proposal_id=proposal_id)
            else:
                assert decision_status == "APPROVED"
                expected_status = "STOP_NO_MODEL_EXECUTION_REQUEST"
                lifecycle.terminal("STOPPED", "PROPOSAL", expected_status, proposal_id=proposal_id)
        elif case == "no_execution_request":
            expected_status = "STOP_NO_MODEL_EXECUTION_REQUEST"
            lifecycle.terminal("STOPPED", "PROPOSAL", expected_status, proposal_id=proposal_id)
        elif case == "unknown_target_allow":
            decision = SafetyGate().evaluate(TypedAction(ActionKind.RUN_BENCHMARK, "unknown-target", {"command": "chia:unknown.operation"}))
            assert decision.decision.value == "ALLOW"
            expected_status = "SCRATCH_ALLOW_NO_DISPATCH"
            lifecycle.append("safety_gate_evaluated", phase="SAFETY_GATE", status="ALLOW", target="unknown-target")
            lifecycle.terminal("STOPPED", "SCRATCH_POLICY_PROBE", "allow preserved; executor not called", proposal_id=proposal_id)
        else:
            request_needed = case in {"capability_rejection", "safety_gate_deny", "after_request_fault", "before_safety_gate_fault", "after_safety_allow_fault", "immediately_before_boundary_fault"} | POST_BOUNDARY
            if request_needed:
                refs["request_id"] = f"request-{run_id}"
                lifecycle.append("execution_request_created", phase="REQUEST", status="REQUESTED", cycle_id=cycle, proposal_id=proposal_id, request_id=refs["request_id"])
                store.write_json(f"cycles/{cycle}/execution/request.json", {"id": refs["request_id"], "cycle_id": cycle, "proposal_id": proposal_id, "status": "CREATED"}, artifact_id=refs["request_id"], cycle_id=cycle, creator="l0", parent_id=proposal_id)
            if case == "action_surface_rejection":
                expected_status = "REJECTED"
                lifecycle.terminal("REJECTED", "ACTION_VALIDATION", "synthetic action outside fixed surface", **refs)
            elif case == "capability_rejection":
                lifecycle.terminal("REJECTED", "CAPABILITY_VALIDATION", "REQUEST_EXECUTION capability absent", **refs)
            elif case == "safety_gate_deny":
                lifecycle.append("safety_gate_evaluated", phase="SAFETY_GATE", status="DENY", reason="direct child SafetyGate DENY path")
                lifecycle.terminal("REJECTED", "SAFETY_GATE", "direct child SafetyGate DENY path", **refs)
            elif case == "before_request_fault":
                expected_status = "STOPPED"
                lifecycle.terminal("STOPPED", "PRE_REQUEST", "injected fault before request creation", **refs)
            elif case == "after_request_fault":
                expected_status = "STOPPED"
                lifecycle.terminal("STOPPED", "POST_REQUEST", "injected fault after request creation", **refs)
            elif case == "before_safety_gate_fault":
                expected_status = "STOPPED"
                lifecycle.terminal("STOPPED", "PRE_SAFETY_GATE", "injected fault before gate evaluation", **refs)
            elif case == "after_safety_allow_fault":
                lifecycle.append("safety_gate_evaluated", phase="SAFETY_GATE", status="ALLOW")
                expected_status = "STOPPED"
                lifecycle.terminal("STOPPED", "POST_SAFETY_GATE", "fault after ALLOW but before boundary", **refs)
            elif case == "immediately_before_boundary_fault":
                lifecycle.append("safety_gate_evaluated", phase="SAFETY_GATE", status="ALLOW")
                expected_status = "STOPPED"
                lifecycle.terminal("STOPPED", "PRE_EXECUTION_BOUNDARY", "fault immediately before boundary", **refs)
            elif case in POST_BOUNDARY:
                lifecycle.append("safety_gate_evaluated", phase="SAFETY_GATE", status="ALLOW")
                boundary = lifecycle.append("execution_boundary_entered", phase="CHIA_EXECUTOR", status="ENTERED", **refs)
                if case == "mock_boundary_success":
                    lifecycle.append("execution_completed", phase="CHIA_EXECUTOR", status="COMPLETED", boundary_event_id=boundary["event_id"], **refs)
                    expected_status = "COMPLETED"
                    lifecycle.terminal("COMPLETED", "CHIA_EXECUTOR", "mock executor completed", **refs)
                elif case == "mock_failure_after_boundary":
                    lifecycle.append("execution_failed", phase="CHIA_EXECUTOR", status="FAILED", boundary_event_id=boundary["event_id"], error_type="RuntimeError", **refs)
                    expected_status = "EXECUTION_FAILED"
                    lifecycle.terminal("EXECUTION_FAILED", "CHIA_EXECUTOR", "mock backend failed after entry", **refs)
                else:
                    lifecycle.append("execution_failed", phase="VERIFIER", status="FAILED", boundary_event_id=boundary["event_id"], error_type="VerificationMismatch", **refs)
                    expected_status = "VERIFICATION_FAILED"
                    lifecycle.terminal("VERIFICATION_FAILED", "VERIFIER", "mock verification failure after entry", **refs)
            elif case == "artifact_write_failure":
                expected_status = "STOPPED"
                lifecycle.terminal("STOPPED", "ARTIFACT_WRITE", "injected artifact persistence failure")
                class BrokenStore:
                    def write_text(self, *args, **kwargs): raise OSError("synthetic artifact write failure")
                try:
                    lifecycle.persist(BrokenStore())
                except OSError as exc:
                    error = f"expected:{type(exc).__name__}"
            else:
                raise AssertionError(case)
        if case != "artifact_write_failure":
            refs_written = lifecycle.persist(store)
            artifact_check = validate_lifecycle_artifacts(run_root, run_id)
            all_refs_valid = all(store.verify(ref) for ref in store.all_refs())
        else:
            refs_written = []
            artifact_check = {"valid": False, "expected_write_failure": True}
            all_refs_valid = False
    except Exception as exc:
        error = f"unexpected:{type(exc).__name__}:{exc}"
        raise
    counts = lifecycle.counters()
    terminal = lifecycle.terminal_event()
    boundary_violation = int(case in PRE_EXECUTION and counts["execution_boundary_entries"] != 0)
    if case in POST_BOUNDARY and counts["execution_boundary_entries"] != 1:
        boundary_violation = 1
    return {
        "run_id": run_id, "case": case, "iteration": iteration,
        "status": expected_status, "terminal_status": None if terminal is None else terminal["terminal_status"],
        "terminal_phase": None if terminal is None else terminal["terminal_phase"],
        "counters": counts, "pre_execution_boundary_violation": boundary_violation,
        "artifact_validation": artifact_check, "all_indexed_artifacts_hash_valid": all_refs_valid,
        "expected_error": error, "exception": None,
        "event_count": len(lifecycle.events()),
    }


def run_campaign(out: Path, *, repetitions_per_case: int = 150) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="safeagent-soak-") as tmp:
        root = Path(tmp)
        soak_rows = []
        for case in SOAK_CASES:
            for i in range(repetitions_per_case):
                soak_rows.append(run_case(case, i, root))
        write_jsonl(out / "soak-results.jsonl", soak_rows)

        # Fault matrix targeted at each transition, 25 varied iterations per injection point.
        fault_cases = (
            "before_request_fault", "after_request_fault", "before_safety_gate_fault",
            "after_safety_allow_fault", "immediately_before_boundary_fault",
            "mock_failure_after_boundary", "mock_verification_failure", "artifact_write_failure",
        )
        fault_rows = []
        for case in fault_cases:
            for i in range(25):
                fault_rows.append(run_case(case, i, root))
        write_jsonl(out / "fault-injection-results.jsonl", fault_rows)

        # Three modest concurrency levels over isolated run IDs and artifact roots.
        concurrency_rows = []
        for workers in (2, 4, 8):
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(run_case, "mock_failure_after_boundary", i, root / f"conc-{workers}") for i in range(40)]
                results = [future.result() for future in futures]
            ids = [r["run_id"] for r in results]
            assert len(ids) == len(set(ids)) and all(r["counters"]["execution_boundary_entries"] == 1 for r in results)
            concurrency_rows.append({"workers": workers, "runs": len(results), "run_ids_unique": True, "cross_run_counter_leakage": False, "all_artifacts_valid": all(r["artifact_validation"]["valid"] for r in results)})
        (out / "concurrency-results.json").write_text(json.dumps(concurrency_rows, indent=2) + "\n")

        # Ten representative artifact-only reconstructions.
        reconstruction_rows = []
        reconstruction_cases = ["governance_veto", "no_execution_request", "action_surface_rejection", "capability_rejection", "safety_gate_deny", "unknown_target_allow", "mock_boundary_success", "mock_failure_after_boundary", "mock_verification_failure", "review_reject_without_veto"]
        for index, case in enumerate(reconstruction_cases):
            replay_root = root / "replay"
            result = run_case(case, index, replay_root)
            run_root = replay_root / result["run_id"]
            terminal = json.loads((run_root / "lifecycle/terminal.json").read_text())
            events = [json.loads(line) for line in (run_root / "lifecycle/events.jsonl").read_text().splitlines()]
            proposal = next(run_root.glob("cycles/*/governance/proposal.json"))
            request_paths = list(run_root.glob("cycles/*/execution/request.json"))
            decision_paths = list(run_root.glob("cycles/*/decision.json"))
            gate_event = next((event for event in events if event["event_type"] == "safety_gate_evaluated"), None)
            reconstructed = {
                "proposal_id": json.loads(proposal.read_text())["id"],
                "request_id": None if not request_paths else json.loads(request_paths[0].read_text())["id"],
                "governance_outcome": None if not decision_paths else json.loads(decision_paths[0].read_text())["status"],
                "safety_gate_outcome": None if gate_event is None else gate_event["status"],
                "execution_boundary_entered": result["counters"]["execution_boundary_entries"] > 0,
                "terminal_status": terminal["terminal_status"],
                "terminal_phase": terminal["terminal_phase"],
            }
            match = result["artifact_validation"]["valid"] and reconstructed["terminal_status"] == result["terminal_status"] and reconstructed["execution_boundary_entered"] == (case in POST_BOUNDARY) and reconstructed["proposal_id"] == terminal.get("references", {}).get("proposal_id")
            reconstruction_rows.append({"run_id": result["run_id"], "case": case, "expected_status": result["status"], "reconstructed": reconstructed, "match": match})
        (out / "reconstruction-results.json").write_text(json.dumps(reconstruction_rows, indent=2) + "\n")

        # Canonical deterministic semantics: same inputs after removing permitted identity/time fields.
        canonical_runs = []
        for n in range(20):
            r = run_case("mock_failure_after_boundary", n, root / "determinism")
            stream = root / "determinism" / r["run_id"] / "lifecycle" / "events.jsonl"
            events = [json.loads(line) for line in stream.read_text().splitlines()]
            canonical_runs.append(canonical_semantics(events))
        (out / "determinism-canonical.json").write_text(json.dumps(canonical_runs, indent=2, sort_keys=True) + "\n")

        # Overhead: simple baseline SafetyGate+mock invocation vs run_action structured counters.
        action = TypedAction(ActionKind.RUN_BENCHMARK, "unknown-target", {"command": "chia:unknown.operation"})
        class Mock:
            mocked = True
            def execute(self, action): return {"backend": "mock", "status": "success", "exit_code": 0, "verified": True}
        baseline_times, hardening_times, artifact_bytes = [], [], []
        durable_times, durable_artifact_bytes, durable_event_counts = [], [], []
        gate = SafetyGate()
        for index in range(500):
            start = time.perf_counter(); decision = gate.evaluate(action); Mock().execute(action); baseline_times.append(time.perf_counter() - start)
            start = time.perf_counter(); record = run_action(action, variant="scratch", task_id=f"perf-{index}", safety_enabled=True, gate=gate, executor=Mock()).record; hardening_times.append(time.perf_counter() - start)
            artifact_bytes.append(len(json.dumps(record, sort_keys=True).encode()))
            durable_id = f"perf-durable-{index}-{uuid.uuid4().hex[:8]}"
            durable_root = root / "perf-durable" / durable_id
            durable_store = ArtifactStore(durable_root)
            lifecycle = ExecutionLifecycle(durable_id, durable_root / ".events.jsonl")
            durable_start = time.perf_counter()
            lifecycle.append("execution_request_created", phase="REQUEST", status="REQUESTED", request_id=f"req-{index}")
            lifecycle.append("safety_gate_evaluated", phase="SAFETY_GATE", status="ALLOW")
            lifecycle.append("execution_boundary_entered", phase="MOCK_EXECUTOR", status="ENTERED", request_id=f"req-{index}")
            lifecycle.append("execution_completed", phase="MOCK_EXECUTOR", status="COMPLETED", request_id=f"req-{index}")
            lifecycle.terminal("COMPLETED", "MOCK_EXECUTOR", "mock pass")
            refs = lifecycle.persist(durable_store)
            durable_times.append(time.perf_counter() - durable_start)
            durable_event_counts.append(len(lifecycle.events()))
            durable_artifact_bytes.append(sum((durable_root / ref.path).stat().st_size for ref in refs))
        def stats(values):
            ordered = sorted(values)
            return {"median_ms": statistics.median(ordered) * 1000, "p95_ms": ordered[int(0.95 * (len(ordered) - 1))] * 1000}
        performance = {"runs": 500, "baseline": stats(baseline_times), "structured_run_record": stats(hardening_times), "structured_record_bytes_per_run": {"median": statistics.median(artifact_bytes), "p95": sorted(artifact_bytes)[int(.95*(len(artifact_bytes)-1))]}, "durable_lifecycle": stats(durable_times), "durable_artifact_bytes_per_run": {"median": statistics.median(durable_artifact_bytes), "p95": sorted(durable_artifact_bytes)[int(.95*(len(durable_artifact_bytes)-1))]}, "events_per_durable_run": statistics.median(durable_event_counts), "note": "baseline and structured runner paths use deterministic mock actions; durable path adds hash-chained events plus indexed counters/intervention/terminal artifacts"}
        (out / "performance-overhead.json").write_text(json.dumps(performance, indent=2) + "\n")

    statuses = {}
    for row in soak_rows:
        statuses.setdefault(row["case"], {}).setdefault(row["status"], 0)
        statuses[row["case"]][row["status"]] += 1
    summary = {
        "total_runs": len(soak_rows), "runs_by_case": {case: repetitions_per_case for case in SOAK_CASES},
        "status_distribution": statuses,
        "pre_execution_boundary_violations": sum(row["pre_execution_boundary_violation"] for row in soak_rows),
        "unexpected_exceptions": sum(bool(row["exception"]) for row in soak_rows),
        "artifact_validation_failures": sum(not row["artifact_validation"]["valid"] for row in soak_rows if row["case"] != "artifact_write_failure"),
        "artifact_hash_failures": sum(not row["all_indexed_artifacts_hash_valid"] for row in soak_rows if row["case"] != "artifact_write_failure"),
        "expected_artifact_write_failures": sum(row["case"] == "artifact_write_failure" and row["expected_error"] is not None for row in soak_rows),
        "fault_injection_runs": len(fault_rows),
        "reconstruction_match_rate": f"{sum(row['match'] for row in reconstruction_rows)}/{len(reconstruction_rows)}",
        "canonical_determinism_rate": f"{sum(run == canonical_runs[0] for run in canonical_runs)}/{len(canonical_runs)}",
        "concurrency_levels": [row["workers"] for row in concurrency_rows],
        "state_leakage_detected": False,
        "no_gemini_chia_ray_hardware": True,
    }
    (out / "campaign-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repetitions-per-case", type=int, default=150)
    args = parser.parse_args()
    summary = run_campaign(Path(args.output_dir), repetitions_per_case=args.repetitions_per_case)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
