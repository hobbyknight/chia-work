from chia_work.council.harness import BootstrapHarness
from chia_work.council.schemas import Direction, L0Decision


def test_l0_l1_l2_l3_file_hierarchy(tmp_path):
    h = BootstrapHarness(tmp_path / "runs" / "smoke")
    mission, cycle = h.start("harmless local smoke objective")
    direction = Direction(id="direction-0", cycle_id=cycle.id, creator="l0", created_at="2026-09-22T00:00:00Z", parent_id=mission.id, objective=mission.objective, requested_roles=["role-a", "role-b"], next_direction="continue")
    decision = L0Decision(id="decision-0", cycle_id=cycle.id, creator="l0", created_at="2026-09-22T00:00:00Z", parent_id=direction.id, direction_id=direction.id, decision="CONTINUE", reason="smoke")
    h.write_l0_outputs(cycle, direction, decision)
    roles = h.make_roles(cycle, direction.requested_roles)
    all_leader = []
    for role in roles:
        l2 = h.create_l2(cycle, role)
        tasks = h.make_tasks(cycle, l2, role, ["read input", "compare metadata", "write evidence"])
        worker_refs = []
        for task in tasks:
            worker_refs.extend(h.run_l3(cycle, l2, task))
        all_leader.extend(h.write_l2_report(cycle, l2, role, worker_refs))
    h.write_l1_outputs(cycle, all_leader)
    required = ["direction.json", "decision.json", "state.json", "task_graph.json", "cycle_summary.md", "open_questions.json", "active_vetoes.json"]
    files = [p.name for p in (tmp_path / "runs" / "smoke" / "cycles" / cycle.id).rglob("*") if p.is_file()]
    for name in required:
        assert name in files
    assert len(list((tmp_path / "runs" / "smoke" / "cycles" / cycle.id / "l3").glob("*/result.json"))) == 6
    assert len(h.store.all_refs()) > 30

