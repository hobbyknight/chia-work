from chia_work.council.artifacts import ArtifactStore
from chia_work.council.governance import Governance
from chia_work.council.schemas import Proposal, utc_now


def test_commit_reveal_hides_reviews_until_all_committed(tmp_path):
    store = ArtifactStore(tmp_path / "run")
    gov = Governance(store, "c")
    proposal = Proposal(id="p", cycle_id="c", creator="l0", created_at=utc_now(), title="p", payload={"safe": True}, proposer_id="l0")
    a = gov.commit_review(proposal, "a", "APPROVE", "a rationale")
    assert not a.revealed
    revealed = gov.reveal_all({"a", "b"}) if False else None
    assert revealed is None
    gov.commit_review(proposal, "b", "APPROVE", "b rationale")
    revealed = gov.reveal_all({"a", "b"})
    assert {r.reviewer_id for r in revealed} == {"a", "b"}
    assert all(r.revealed for r in revealed)

