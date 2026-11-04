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


# ── Failure handling ──────────────────────────────────────────────────────────

class FakeProc:
    """Stands in for an ffmpeg process."""
    def __init__(self, returncode=0, stderr=b"", writes=None, out=None):
        self.returncode, self._stderr = returncode, stderr
        if writes is not None and out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(writes)

    def communicate(self, timeout=None):
        return b"", self._stderr

    def poll(self):
        return self.returncode

    def kill(self):
        pass


def test_a_nonzero_exit_is_a_failure(rec, monkeypatch, tmp_path):
    out = tmp_path / "clip.mp4"
    monkeypatch.setattr(rec.subprocess, "Popen",
                        lambda *a, **k: FakeProc(returncode=1, stderr=b"Connection refused"))
    ok, reason = rec.run_ffmpeg("cam", out, 5)
    assert ok is False
    assert "Connection refused" in reason


def test_an_empty_clip_is_a_failure(rec, monkeypatch, tmp_path):
    """ffmpeg can exit 0 having written nothing — that was logged as "saved"."""
    out = tmp_path / "clip.mp4"
    monkeypatch.setattr(rec.subprocess, "Popen",
                        lambda *a, **k: FakeProc(returncode=0, writes=b"tiny", out=out))
    ok, reason = rec.run_ffmpeg("cam", out, 5)
    assert ok is False
    assert "empty" in reason
    assert not out.exists(), "the stub file should be cleaned up"


def test_a_missing_file_is_a_failure(rec, monkeypatch, tmp_path):
    monkeypatch.setattr(rec.subprocess, "Popen", lambda *a, **k: FakeProc(returncode=0))
    ok, reason = rec.run_ffmpeg("cam", tmp_path / "clip.mp4", 5)
    assert ok is False and "no file" in reason


def test_a_real_clip_succeeds(rec, monkeypatch, tmp_path):
    out = tmp_path / "clip.mp4"
    payload = b"x" * (rec.MIN_CLIP_BYTES + 1)
    monkeypatch.setattr(rec.subprocess, "Popen",
                        lambda *a, **k: FakeProc(returncode=0, writes=payload, out=out))
    assert rec.run_ffmpeg("cam", out, 5) == (True, "")


def test_a_hung_ffmpeg_is_killed(rec, monkeypatch, tmp_path):
    class Hung(FakeProc):
        def communicate(self, timeout=None):
            if timeout is not None:
                raise rec.subprocess.TimeoutExpired("ffmpeg", timeout)
            return b"", b""

    monkeypatch.setattr(rec.subprocess, "Popen", lambda *a, **k: Hung())
    ok, reason = rec.run_ffmpeg("cam", tmp_path / "clip.mp4", 1)
    assert ok is False and "time limit" in reason


def test_recording_retries_before_giving_up(rec, monkeypatch, tmp_path):
    """Ring streams often are not up yet the instant an event fires."""
    monkeypatch.setattr(rec, "RETRY_DELAY", 0)
    monkeypatch.setattr(rec, "VIDEO_PATH", tmp_path)
    attempts = []

    def fail(device_id, out, duration):
        attempts.append(device_id)
        return False, "stream not ready"

    monkeypatch.setattr(rec, "run_ffmpeg", fail)
    rec.record("cam", "motion")
    for t in rec.threading.enumerate():
        if t is not rec.threading.current_thread():
            t.join(timeout=5)

    assert len(attempts) == rec.RECORD_ATTEMPTS


def test_a_full_disk_stops_recording(rec, monkeypatch, tmp_path):
    monkeypatch.setattr(rec, "VIDEO_PATH", tmp_path)
    monkeypatch.setattr(rec, "free_bytes", lambda path: 1024)
    started = []
    monkeypatch.setattr(rec, "run_ffmpeg", lambda *a: started.append(a) or (True, ""))

    rec.record("cam", "motion")

    assert started == []


def test_unknown_free_space_does_not_block_recording(rec, monkeypatch, tmp_path):
    monkeypatch.setattr(rec, "VIDEO_PATH", tmp_path)
    monkeypatch.setattr(rec, "free_bytes", lambda path: -1)
    monkeypatch.setattr(rec, "run_ffmpeg", lambda *a: (True, ""))
    rec.record("cam", "motion")
    for t in rec.threading.enumerate():
        if t is not rec.threading.current_thread():
            t.join(timeout=5)
