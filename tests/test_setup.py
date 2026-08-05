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
