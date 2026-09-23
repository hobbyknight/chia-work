"""Deterministic governance: commit/reveal, veto enforcement, and decisions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .artifacts import ArtifactError, ArtifactStore
from .schemas import DecisionRecord, IndependentReview, Proposal, VetoRecord, utc_now


class GovernanceError(RuntimeError):
    pass


class Governance:
    def __init__(self, store: ArtifactStore, cycle_id: str, creator: str = "l1-coordinator"):
        self.store = store
        self.cycle_id = cycle_id
        self.creator = creator
        self._reviews: dict[str, IndependentReview] = {}
        self._revealed = False
        self._vetoes: dict[str, VetoRecord] = {}
        self._decisions: dict[str, DecisionRecord] = {}

    @staticmethod
    def commit_digest(verdict: str, rationale: str) -> str:
        return hashlib.sha256(json.dumps({"rationale": rationale, "verdict": verdict}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def commit_review(self, proposal: Proposal, reviewer_id: str, verdict: str, rationale: str) -> IndependentReview:
        if self._revealed:
            raise GovernanceError("review commit phase is closed")
        review = IndependentReview(
            id=f"review-{proposal.id}-{reviewer_id}", cycle_id=self.cycle_id, creator=reviewer_id, created_at=utc_now(),
            parent_id=proposal.id, proposal_id=proposal.id, reviewer_id=reviewer_id,
            verdict=verdict, rationale=rationale, commit_sha256=self.commit_digest(verdict, rationale), revealed=False,
        )
        self._reviews[review.id] = review
        return review

    def reveal_all(self, required_reviewers: set[str]) -> list[IndependentReview]:
        if {r.reviewer_id for r in self._reviews.values()} != required_reviewers:
            raise GovernanceError("cannot reveal before all required independent reviews are committed")
        self._revealed = True
        revealed: list[IndependentReview] = []
        for review in self._reviews.values():
            if self.commit_digest(review.verdict, review.rationale) != review.commit_sha256:
                raise GovernanceError(f"commit mismatch for {review.id}")
            review.revealed = True
            revealed.append(review)
        return revealed

    def record_veto(self, proposal: Proposal, vetoer_id: str, reason: str, allowed: bool) -> VetoRecord:
        if not allowed:
            raise GovernanceError("veto capability not granted")
        veto = VetoRecord(
            id=f"veto-{proposal.id}-{vetoer_id}", cycle_id=self.cycle_id, creator=vetoer_id, created_at=utc_now(),
            parent_id=proposal.id, proposal_id=proposal.id, vetoer_id=vetoer_id, reason=reason, valid=True,
        )
        self._vetoes[veto.id] = veto
        return veto

    def decide(self, proposal: Proposal, review_ids: list[str]) -> DecisionRecord:
        if not self._revealed:
            raise GovernanceError("cannot decide before reveal")
        vetoes = [v for v in self._vetoes.values() if v.proposal_id == proposal.id and v.valid]
        status = "REJECTED" if vetoes else "APPROVED"
        decision = DecisionRecord(
            id=f"decision-{proposal.id}", cycle_id=self.cycle_id, creator=self.creator, created_at=utc_now(),
            parent_id=proposal.id, proposal_id=proposal.id, status=status, review_refs=review_ids,
            veto_refs=[v.id for v in vetoes], rationale="valid veto recorded" if vetoes else "independent reviews revealed", immutable=True,
        )
        self._decisions[decision.id] = decision
        return decision

    def persist_decision(self, decision: DecisionRecord) -> None:
        self.store.write_json(
            f"cycles/{self.cycle_id}/decisions/{decision.id}.json", decision,
            artifact_id=decision.id, cycle_id=self.cycle_id, creator=decision.creator,
            parent_id=decision.parent_id, lineage_refs=decision.review_refs + decision.veto_refs, kind="decision",
        )

    def vetoes_for(self, proposal_id: str) -> list[VetoRecord]:
        return [v for v in self._vetoes.values() if v.proposal_id == proposal_id and v.valid]

