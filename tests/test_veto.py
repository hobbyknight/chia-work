from contextlib import contextmanager

from chia_work.council.artifacts import ArtifactStore
from chia_work.council.governance import Governance, GovernanceError
from chia_work.council.schemas import Proposal, utc_now


@contextmanager
def raises(expected):
    try:
        yield
    except expected:
        return
    raise AssertionError(f"expected {expected.__name__}")


def test_veto_forces_rejection_and_cannot_be_removed(tmp_path):
    gov = Governance(ArtifactStore(tmp_path / "run"), "c")
    p = Proposal(id="p", cycle_id="c", creator="l0", created_at=utc_now(), title="p", payload={}, proposer_id="l0")
    a = gov.commit_review(p, "a", "APPROVE", "ok")
    gov.commit_review(p, "b", "APPROVE", "ok")
    gov.reveal_all({"a", "b"})
    veto = gov.record_veto(p, "b", "policy boundary", allowed=True)
    d = gov.decide(p, [a.id, "review-p-b"])
    assert d.status == "REJECTED"
    assert d.veto_refs == [veto.id]
    with raises(GovernanceError):
        gov.record_veto(p, "x", "not allowed", allowed=False)
    assert gov.vetoes_for(p.id) == [veto]
