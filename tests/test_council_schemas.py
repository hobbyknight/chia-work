from chia_work.council.schemas import Mission, utc_now


def test_versioned_mission_is_stable_json():
    mission = Mission(id="m", cycle_id="c", creator="user", created_at=utc_now(), run_id="r", objective="harmless")
    payload = mission.model_dump(mode="json")
    assert payload["schema_version"] == 1
    assert '"objective":"harmless"' in mission.stable_json()

