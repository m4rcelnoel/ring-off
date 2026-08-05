"""The guided setup endpoints."""

import asyncio
import json


def get(coro):
    return asyncio.run(coro)


# ── State ─────────────────────────────────────────────────────────────────────

def test_a_fresh_install_needs_setup(app):
    state = get(app.setup_state())
    assert state["complete"] is False
    assert state["ring_authenticated"] is False
    assert state["cameras_found"] == 0


def test_completing_setup_sticks(app):
    get(app.setup_finish())
    assert get(app.setup_state())["complete"] is True


def test_reset_sends_the_user_back_through_the_wizard(app):
    get(app.setup_finish())
    get(app.setup_reset())
    assert get(app.setup_state())["complete"] is False


def test_camera_count_excludes_chimes(app, mqtt_handler):
    mqtt_handler("ring/loc/camera/cam1/info/state", json.dumps({"batteryLevel": 50}))
    mqtt_handler("ring/loc/chime/ch1/info/state", json.dumps({"wirelessSignal": -40}))
    assert get(app.setup_state())["cameras_found"] == 1


# ── Adoption of pre-wizard installs ───────────────────────────────────────────

def test_an_authenticated_install_is_adopted(app):
    """Upgrading users must not be dragged back through onboarding."""
    app.save_ring_token("TOKEN")
    app.adopt_existing_install()
    assert get(app.setup_state())["complete"] is True


def test_an_unauthenticated_install_is_not_adopted(app):
    app.adopt_existing_install()
    assert get(app.setup_state())["complete"] is False


def test_adoption_never_undoes_a_reset(app):
    """Someone with a token who clicks "Run setup again" must reach the wizard."""
    app.save_ring_token("TOKEN")
    get(app.setup_finish())
    get(app.setup_reset())
    assert get(app.setup_state())["complete"] is False


# ── Preflight ─────────────────────────────────────────────────────────────────

def test_preflight_reports_every_service(app, monkeypatch):
    monkeypatch.setattr(app, "_tcp_open", lambda host, port, timeout=2.0: True)
    result = get(app.setup_preflight())
    assert {c["key"] for c in result["checks"]} == {
        "mqtt", "ring_mqtt", "go2rtc", "config", "videos"
    }


def test_failing_checks_carry_a_hint(app, monkeypatch):
    monkeypatch.setattr(app, "_tcp_open", lambda host, port, timeout=2.0: False)
    result = get(app.setup_preflight())
    for check in result["checks"]:
        if not check["ok"]:
            assert check["hint"], f"{check['key']} failed without telling the user why"


def test_a_missing_broker_blocks_setup(app, monkeypatch):
    monkeypatch.setattr(app, "_tcp_open", lambda host, port, timeout=2.0: False)
    monkeypatch.setattr(app, "_mqtt_connected", False)
    result = get(app.setup_preflight())
    assert result["ok"] is False
    assert next(c for c in result["checks"] if c["key"] == "mqtt")["ok"] is False


def test_go2rtc_being_down_does_not_block_setup(app, monkeypatch):
    """Everything except live video still works without go2rtc."""
    monkeypatch.setattr(app, "_tcp_open", lambda host, port, timeout=2.0: True)
    result = get(app.setup_preflight())

    go2rtc = next(c for c in result["checks"] if c["key"] == "go2rtc")
    assert go2rtc["ok"] is False, "no go2rtc is running in the test environment"
    assert go2rtc["required"] is False
    assert result["ok"] is True


def test_write_checks_use_the_real_filesystem(app, monkeypatch):
    monkeypatch.setattr(app, "_tcp_open", lambda host, port, timeout=2.0: True)
    result = get(app.setup_preflight())
    assert next(c for c in result["checks"] if c["key"] == "config")["ok"] is True
    assert next(c for c in result["checks"] if c["key"] == "videos")["ok"] is True


def test_unwritable_paths_are_reported(app, monkeypatch):
    monkeypatch.setattr(app, "_tcp_open", lambda host, port, timeout=2.0: True)
    monkeypatch.setattr(app, "GO2RTC_CONFIG", app.Path("/proc/nope/go2rtc.yaml"))
    result = get(app.setup_preflight())
    assert next(c for c in result["checks"] if c["key"] == "config")["ok"] is False
    assert result["ok"] is False


# ── Discovery ─────────────────────────────────────────────────────────────────

def test_discovery_is_empty_before_anything_arrives(app):
    found = get(app.setup_discovered())
    assert found["cameras"] == [] and found["chimes"] == []


def test_discovered_devices_are_split_by_type(app, mqtt_handler):
    mqtt_handler("ring/loc/camera/aabbcc112233/info/state",
                 json.dumps({"batteryLevel": 77, "wirelessSignal": -50}))
    mqtt_handler("ring/loc/chime/ddeeff445566/info/state",
                 json.dumps({"wirelessSignal": -40}))

    found = get(app.setup_discovered())

    assert len(found["cameras"]) == 1
    assert found["cameras"][0]["battery_level"] == 77
    assert found["cameras"][0]["name"] == "Camera 112233"
    assert len(found["chimes"]) == 1
    assert found["chimes"][0]["name"] == "Chime 5566"


def test_discovery_reports_snapshot_availability(app, mqtt_handler):
    mqtt_handler("ring/loc/camera/cam1/info/state", json.dumps({}))
    assert get(app.setup_discovered())["cameras"][0]["has_snapshot"] is False

    mqtt_handler("ring/loc/camera/cam1/snapshot/image", b"\xff\xd8jpeg")
    assert get(app.setup_discovered())["cameras"][0]["has_snapshot"] is True


def test_configured_cameras_survive_a_restart(app):
    """device_states is empty until MQTT republishes, but an install that is
    already configured must not look like it has no cameras."""
    app.ensure_go2rtc_config()
    app.GO2RTC_CONFIG.write_text(
        app.GO2RTC_CONFIG.read_text() + "  front_door: rtsp://ring-mqtt:8554/aabbcc112233_live\n"
    )
    found = get(app.setup_discovered())
    assert [c["device_id"] for c in found["cameras"]] == ["aabbcc112233"]


def test_disabled_cameras_are_still_listed(app):
    """Otherwise there is no way to switch one back on."""
    settings = app.load_settings()
    settings["disabled_cameras"] = ["aabbcc112233"]
    app.save_settings(settings)
    found = get(app.setup_discovered())
    assert found["cameras"][0]["enabled"] is False


def test_a_reset_survives_a_restart(app):
    """adopt_existing_install() runs on every startup; it must not quietly
    undo the user clicking "Run setup again"."""
    app.save_ring_token("TOKEN")
    get(app.setup_finish())
    get(app.setup_reset())

    app.adopt_existing_install()          # as if the webapp restarted

    assert get(app.setup_state())["complete"] is False


def test_adoption_only_happens_once(app):
    app.save_ring_token("TOKEN")
    app.adopt_existing_install()
    assert get(app.setup_state())["complete"] is True

    get(app.setup_reset())
    app.adopt_existing_install()
    assert get(app.setup_state())["complete"] is False


# ── Test notifications ────────────────────────────────────────────────────────

def test_a_missing_url_is_rejected(app):
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as err:
        get(app.setup_test_notification(app.TestNotificationRequest()))
    assert err.value.status_code == 400


def test_a_successful_test_reports_ok(app, monkeypatch):
    async def fake(url, title, body):
        return True, "HTTP 200"
    monkeypatch.setattr(app, "post_notification", fake)
    result = get(app.setup_test_notification(
        app.TestNotificationRequest(notify_url="https://ntfy.sh/topic")))
    assert result == {"ok": True, "detail": "HTTP 200"}


def test_a_failing_test_surfaces_the_reason(app, monkeypatch):
    """A wrong URL used to fail silently into the log."""
    async def fake(url, title, body):
        return False, "HTTP 404 — topic not found"
    monkeypatch.setattr(app, "post_notification", fake)
    result = get(app.setup_test_notification(
        app.TestNotificationRequest(notify_url="https://ntfy.sh/nope")))
    assert result["ok"] is False
    assert "404" in result["detail"]


def test_the_saved_url_is_used_when_none_is_supplied(app, monkeypatch):
    settings = app.load_settings()
    settings["notify_url"] = "https://ntfy.sh/saved"
    app.save_settings(settings)

    seen = {}
    async def fake(url, title, body):
        seen["url"] = url
        return True, "HTTP 200"
    monkeypatch.setattr(app, "post_notification", fake)

    get(app.setup_test_notification(app.TestNotificationRequest()))
    assert seen["url"] == "https://ntfy.sh/saved"


def test_gotify_and_ntfy_use_different_shapes(app, monkeypatch):
    sent = []

    class Response:
        status_code = 200
        text = ""

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, **kwargs):
            sent.append(kwargs)
            return Response()

    monkeypatch.setattr(app.httpx, "AsyncClient", lambda **kw: Client())

    get(app.post_notification("https://gotify.host/message?token=x", "T", "B"))
    assert "json" in sent[-1]

    get(app.post_notification("https://ntfy.sh/topic", "T", "B"))
    assert sent[-1]["headers"]["Title"] == "T"


def test_an_unreachable_host_is_reported_not_raised(app, monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, **kwargs): raise OSError("name resolution failed")

    monkeypatch.setattr(app.httpx, "AsyncClient", lambda **kw: Client())
    ok, detail = get(app.post_notification("https://ntfy.example/topic", "T", "B"))
    assert ok is False and "name resolution failed" in detail


def test_setting_a_password_would_lock_setup_completion(app):
    """The wizard sets the dashboard password on its final screen. Without
    logging straight back in, the very next request is blocked by the password
    just set and setup could never be marked complete."""
    from fastapi.testclient import TestClient
    session = TestClient(app.app)

    session.post("/api/app/set-password", json={"password": "hunter2"})
    assert session.post("/api/setup/complete", json={}).status_code == 401

    session.post("/api/app/login", json={"password": "hunter2"})
    assert session.post("/api/setup/complete", json={}).status_code == 200
