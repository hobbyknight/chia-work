from chia_work.bridge.council_chia_bridge import BridgeValidationError, validate_request


def request(decision_status="APPROVED", veto_refs=None, extra=None):
    payload = {
        "execution_request": {"id": "er", "cycle_id": "c", "creator": "l1", "created_at": "2026-09-22T00:00:00Z", "decision_record_id": "d", "typed_action": {"schema_version": 1, "action_kind": "VALIDATE_ONLY_TEST", "payload": {}}, "requested_by": "l1", "capability_grant_id": "g"},
        "decision_record": {"id": "d", "cycle_id": "c", "creator": "l1", "created_at": "2026-09-22T00:00:00Z", "proposal_id": "p", "status": decision_status, "review_refs": [], "veto_refs": veto_refs or [], "rationale": "smoke", "immutable": True},
        "capability_grant": {"capabilities": ["REQUEST_EXECUTION"]},
    }
    if extra:
        payload.update(extra)
    return payload


def test_validate_only_accepts_authorized_request():
    result = validate_request(request())
    assert result["status"] == "VALIDATED"
    assert result["hardware_executed"] is False


def test_validate_only_rejects_missing_decision_veto_and_shell():
    for payload in [request("REJECTED"), request(veto_refs=["v"]), request(extra={"shell": "rm -rf /"})]:
        try:
            validate_request(payload)
        except BridgeValidationError:
            pass
        else:
            raise AssertionError("invalid bridge request was accepted")

