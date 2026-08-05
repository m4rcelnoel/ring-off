"""The recorder builds its own RTSP URLs and must agree with the webapp."""

import json

import pytest


@pytest.fixture
def rec(tmp_path, monkeypatch):
    import recorder

    monkeypatch.setattr(recorder, "RING_MQTT_CONFIG", tmp_path / "config.json")
    monkeypatch.setattr(recorder, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(recorder, "VIDEO_PATH", tmp_path / "videos")
    monkeypatch.setattr(recorder, "RTSP_USER_ENV", "")
    monkeypatch.setattr(recorder, "RTSP_PASS_ENV", "")
    return recorder


def test_no_credentials_produces_no_userinfo(rec):
    assert rec.rtsp_url("abc123") == "rtsp://ring-mqtt:8554/abc123_live"


def test_credentials_are_percent_encoded(rec):
    rec.RING_MQTT_CONFIG.write_text(json.dumps(
        {"livestream_user": "ring/user", "livestream_pass": "p@ss:w0rd!"}))
    assert rec.rtsp_url("abc123") == (
        "rtsp://ring%2Fuser:p%40ss%3Aw0rd%21@ring-mqtt:8554/abc123_live"
    )


def test_env_fallback_encodes_the_at_sign(rec, monkeypatch):
    monkeypatch.setattr(rec, "RTSP_USER_ENV", "me@example.com")
    monkeypatch.setattr(rec, "RTSP_PASS_ENV", "hunter2")
    assert rec.rtsp_url("abc") == "rtsp://me%40example.com:hunter2@ring-mqtt:8554/abc_live"


def test_ring_mqtt_config_wins_over_the_environment(rec, monkeypatch):
    monkeypatch.setattr(rec, "RTSP_USER_ENV", "env-user")
    monkeypatch.setattr(rec, "RTSP_PASS_ENV", "env-pass")
    rec.RING_MQTT_CONFIG.write_text(json.dumps(
        {"livestream_user": "cfg-user", "livestream_pass": "cfg-pass"}))
    assert "cfg-user:cfg-pass@" in rec.rtsp_url("abc")


def test_a_corrupt_config_falls_back_to_the_environment(rec, monkeypatch):
    monkeypatch.setattr(rec, "RTSP_USER_ENV", "env-user")
    monkeypatch.setattr(rec, "RTSP_PASS_ENV", "env-pass")
    rec.RING_MQTT_CONFIG.write_text("{not json")
    assert "env-user:env-pass@" in rec.rtsp_url("abc")


def test_settings_defaults_apply_without_a_file(rec):
    settings = rec.load_settings()
    assert settings["record_motion"] is True
    assert settings["record_duration"] == 60


def test_settings_are_read_from_the_shared_file(rec):
    """The webapp writes this file; the recorder re-reads it on every event."""
    rec.SETTINGS_FILE.write_text(json.dumps({"record_duration": 120}))
    assert rec.load_settings()["record_duration"] == 120
    assert rec.load_settings()["record_ding"] is True


def test_recording_respects_the_motion_toggle(rec, monkeypatch):
    rec.SETTINGS_FILE.write_text(json.dumps({"record_motion": False}))
    started = []
    monkeypatch.setattr(rec.subprocess, "Popen", lambda *a, **k: started.append(a))

    rec.record("abc123", "motion")

    assert started == []


def test_recording_respects_the_ding_toggle(rec, monkeypatch):
    rec.SETTINGS_FILE.write_text(json.dumps({"record_ding": False}))
    started = []
    monkeypatch.setattr(rec.subprocess, "Popen", lambda *a, **k: started.append(a))

    rec.record("abc123", "ding")

    assert started == []
