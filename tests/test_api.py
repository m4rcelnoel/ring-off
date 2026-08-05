"""Ring token storage, settings, recordings and the auth middleware."""

import asyncio
import json

import pytest
from fastapi import HTTPException


# ── Ring token ────────────────────────────────────────────────────────────────

def test_token_is_written_where_ring_mqtt_reads_it(app):
    """ring-mqtt loads the token from ring-state.json; config.json has no
    ring_token field, so writing it there left ring-mqtt unauthenticated
    while the dashboard reported success."""
    app.save_ring_token("TOKEN123")

    state = json.loads(app.RING_MQTT_STATE.read_text())
    assert state["ring_token"] == "TOKEN123"
    assert set(state) == {"ring_token", "systemId", "devices"}
    assert len(state["systemId"]) == 64, "ring-mqtt expects a sha256 hex systemId"


def test_saving_a_token_creates_the_directory(app):
    assert not app.RING_MQTT_STATE.parent.exists()
    app.save_ring_token("TOKEN123")
    assert app.RING_MQTT_STATE.exists()


def test_existing_state_is_preserved(app):
    app.RING_MQTT_STATE.parent.mkdir(parents=True)
    app.RING_MQTT_STATE.write_text(json.dumps(
        {"ring_token": "old", "systemId": "abc", "devices": {"d": 1}}))

    app.save_ring_token("new")

    state = json.loads(app.RING_MQTT_STATE.read_text())
    assert state["ring_token"] == "new"
    assert state["systemId"] == "abc"
    assert state["devices"] == {"d": 1}


def test_token_presence(app, ring_config):
    assert app.ring_token_present() is False
    app.save_ring_token("TOKEN123")
    assert app.ring_token_present() is True


def test_older_ring_mqtt_config_token_still_counts(app, ring_config):
    ring_config(ring_token="legacy")
    assert app.ring_token_present() is True


# ── Settings ──────────────────────────────────────────────────────────────────

def save(app, **overrides):
    request = app.SettingsRequest(**overrides)
    asyncio.run(app.save_settings_route(request))
    return app.load_settings()


def test_clip_duration_is_clamped(app):
    assert save(app, record_duration=5)["record_duration"] == 10
    assert save(app, record_duration=9000)["record_duration"] == 300


def test_retention_cannot_be_negative(app):
    assert save(app, retention_days=-5)["retention_days"] == 0


def test_battery_threshold_is_clamped(app):
    assert save(app, low_battery_threshold=0)["low_battery_threshold"] == 1
    assert save(app, low_battery_threshold=500)["low_battery_threshold"] == 100


def test_ha_token_is_kept_when_not_resubmitted(app):
    """The UI sends the token only when it changes."""
    save(app, ha_url="http://ha:8123", ha_token="secret")
    assert save(app, ha_url="http://ha:8123")["ha_token"] == "secret"


def test_settings_response_hides_the_ha_token(app):
    save(app, ha_url="http://ha:8123", ha_token="secret")
    body = asyncio.run(app.get_settings())
    assert body["ha_token_set"] is True
    assert "ha_token" not in body


# ── Recordings ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("device_id,filename", [
    ("..", "clip.mp4"),
    ("cam", "../../etc/passwd"),
    ("cam/nested", "clip.mp4"),
    ("cam", "a/b.mp4"),
])
def test_path_traversal_is_rejected(app, device_id, filename):
    with pytest.raises(HTTPException) as err:
        asyncio.run(app.delete_recording(device_id, filename))
    assert err.value.status_code == 400


def test_deleting_a_missing_clip_is_a_404(app):
    with pytest.raises(HTTPException) as err:
        asyncio.run(app.delete_recording("cam", "nope.mp4"))
    assert err.value.status_code == 404


def test_recordings_are_listed_with_their_kind(app):
    clips = app.VIDEO_PATH / "cam1"
    clips.mkdir(parents=True)
    (clips / "20260101_120000_motion.mp4").write_bytes(b"x")
    (clips / "20260101_130000_ding.mp4").write_bytes(b"yy")

    listed = {c["filename"]: c for c in asyncio.run(app.get_recordings())}

    assert listed["20260101_120000_motion.mp4"]["kind"] == "motion"
    assert listed["20260101_130000_ding.mp4"]["kind"] == "ding"
    assert listed["20260101_130000_ding.mp4"]["size"] == 2


def test_recordings_are_empty_without_a_video_directory(app):
    assert asyncio.run(app.get_recordings()) == []


# ── Auth middleware ───────────────────────────────────────────────────────────

def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app.app)      # no context manager: skips lifespan/MQTT


def test_everything_is_open_without_a_password(app):
    assert client(app).get("/api/status").status_code == 200


def test_api_is_blocked_once_a_password_is_set(app):
    asyncio.run(app.set_password(app.SetPasswordRequest(password="hunter2")))
    assert client(app).get("/api/settings").status_code == 401


def test_login_endpoints_stay_reachable_when_locked(app):
    asyncio.run(app.set_password(app.SetPasswordRequest(password="hunter2")))
    assert client(app).get("/api/app/status").status_code == 200


def test_a_correct_password_unlocks_the_api(app):
    asyncio.run(app.set_password(app.SetPasswordRequest(password="hunter2")))
    session = client(app)

    assert session.post("/api/app/login", json={"password": "hunter2"}).status_code == 200
    assert session.get("/api/settings").status_code == 200


def test_a_wrong_password_is_rejected(app):
    asyncio.run(app.set_password(app.SetPasswordRequest(password="hunter2")))
    response = client(app).post("/api/app/login", json={"password": "wrong"})
    assert response.status_code == 401


def test_clearing_the_password_reopens_the_api(app):
    asyncio.run(app.set_password(app.SetPasswordRequest(password="hunter2")))
    asyncio.run(app.set_password(app.SetPasswordRequest(password="")))
    assert client(app).get("/api/settings").status_code == 200
