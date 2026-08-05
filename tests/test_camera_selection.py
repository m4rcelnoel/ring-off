"""Naming, enabling and disabling cameras during setup."""

import asyncio
import json


def select(app, *cameras):
    """cameras: (device_id, name, enabled) tuples."""
    request = app.CameraSelectionRequest(cameras=[
        {"device_id": d, "name": n, "enabled": e} for d, n, e in cameras
    ])
    return asyncio.run(app.save_camera_config(request))


# ── Slugs ─────────────────────────────────────────────────────────────────────

def test_friendly_names_become_safe_stream_names(app):
    assert app._stream_slug("Front Door", "abc", set()) == "front_door"


def test_accents_are_folded_rather_than_mangled(app):
    """A German name must not turn into 'vordert_r'."""
    assert app._stream_slug("Vordertür", "abc", set()) == "vordertur"


def test_a_nameless_camera_falls_back_to_its_id(app):
    assert app._stream_slug("!!!", "aabbcc112233", set()) == "camera_112233"


def test_duplicate_names_are_disambiguated(app):
    taken = set()
    assert app._stream_slug("Front Door", "a", taken) == "front_door"
    assert app._stream_slug("Front Door", "b", taken) == "front_door_2"


# ── Applying a selection ──────────────────────────────────────────────────────

def test_named_cameras_are_written_to_go2rtc(app):
    select(app, ("aabbcc112233", "Front Door", True))
    assert app.go2rtc_streams() == {"front_door": "aabbcc112233"}


def test_the_friendly_name_is_stored_for_the_dashboard(app):
    select(app, ("aabbcc112233", "Vordertür", True))
    assert app.load_settings()["camera_names"]["aabbcc112233"] == "Vordertür"


def test_the_dashboard_shows_the_friendly_name(app, monkeypatch):
    """The stream slug is ASCII; the displayed name must not be."""
    select(app, ("aabbcc112233", "Vordertür", True))

    class Response:
        @staticmethod
        def json():
            return {"vordertur": {"producers": []}}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url): return Response()

    monkeypatch.setattr(app.httpx, "AsyncClient", lambda **kw: Client())
    cameras = asyncio.run(app.get_cameras())
    assert cameras[0]["name"] == "Vordertür"


def test_renaming_replaces_the_old_entry(app):
    select(app, ("aabbcc112233", "Front Door", True))
    select(app, ("aabbcc112233", "Back Door", True))
    assert app.go2rtc_streams() == {"back_door": "aabbcc112233"}


def test_disabling_removes_the_stream(app):
    select(app, ("aabbcc112233", "Front Door", True))
    select(app, ("aabbcc112233", "Front Door", False))
    assert app.go2rtc_streams() == {}
    assert app.load_settings()["disabled_cameras"] == ["aabbcc112233"]


def test_a_disabled_camera_is_not_rediscovered(app, mqtt_handler):
    """Auto-discovery would otherwise re-add it on the next MQTT message."""
    select(app, ("aabbcc112233", "Front Door", False))
    mqtt_handler("ring/loc/camera/aabbcc112233/info/state", json.dumps({"batteryLevel": 50}))
    assert app.go2rtc_streams() == {}


def test_re_enabling_brings_it_back(app):
    select(app, ("aabbcc112233", "Front Door", False))
    select(app, ("aabbcc112233", "Front Door", True))
    assert app.go2rtc_streams() == {"front_door": "aabbcc112233"}
    assert app.load_settings()["disabled_cameras"] == []


def test_multiple_cameras_keep_distinct_streams(app):
    select(app,
           ("aaaaaa111111", "Front Door", True),
           ("bbbbbb222222", "Back Door", True))
    assert app.go2rtc_streams() == {
        "front_door": "aaaaaa111111",
        "back_door": "bbbbbb222222",
    }


def test_an_empty_name_falls_back_to_the_device_id(app):
    select(app, ("aabbcc112233", "   ", True))
    assert app.load_settings()["camera_names"]["aabbcc112233"] == "Camera 112233"


def test_foreign_streams_survive_a_selection(app):
    """Hand-added entries for other hardware must not be dropped."""
    app.ensure_go2rtc_config()
    app.GO2RTC_CONFIG.write_text(
        app.GO2RTC_CONFIG.read_text() + "  garage: rtsp://192.168.1.50:554/other_live\n"
    )
    select(app, ("aabbcc112233", "Front Door", True))
    text = app.GO2RTC_CONFIG.read_text()
    assert "rtsp://192.168.1.50:554/other_live" in text
    assert "front_door" in text


def test_comments_survive_a_selection(app):
    app.ensure_go2rtc_config()
    select(app, ("aabbcc112233", "Front Door", True))
    assert "# Cameras are added here automatically" in app.GO2RTC_CONFIG.read_text()


def test_stream_urls_use_the_go2rtc_host(app, monkeypatch):
    """Written for go2rtc to resolve, not for this process."""
    monkeypatch.setattr(app, "RTSP_HOST", "localhost")
    select(app, ("aabbcc112233", "Front Door", True))
    assert "rtsp://ring-mqtt:8554/aabbcc112233_live" in app.GO2RTC_CONFIG.read_text()


def test_the_selection_is_reported_back(app):
    result = select(app,
                    ("aaaaaa111111", "Front", True),
                    ("bbbbbb222222", "Back", False))
    assert result == {"enabled": 1, "disabled": 1}


# ── Discovery reflects the saved selection ────────────────────────────────────

def test_discovery_shows_saved_names_and_toggles(app, mqtt_handler):
    mqtt_handler("ring/loc/camera/aabbcc112233/info/state", json.dumps({}))
    mqtt_handler("ring/loc/camera/ddeeff445566/info/state", json.dumps({}))
    select(app, ("aabbcc112233", "Front Door", True), ("ddeeff445566", "Shed", False))

    found = {c["device_id"]: c for c in asyncio.run(app.setup_discovered())["cameras"]}

    assert found["aabbcc112233"]["name"] == "Front Door"
    assert found["aabbcc112233"]["enabled"] is True
    assert found["ddeeff445566"]["enabled"] is False


# ── Managing cameras outside setup ────────────────────────────────────────────

def test_camera_config_is_readable_without_the_wizard(app, mqtt_handler):
    """Settings needs the same list the wizard shows."""
    mqtt_handler("ring/loc/camera/aabbcc112233/info/state", json.dumps({"batteryLevel": 60}))
    rows = asyncio.run(app.get_camera_config())
    assert rows[0]["device_id"] == "aabbcc112233"
    assert rows[0]["name"] == "Camera 112233"
    assert rows[0]["enabled"] is True
    assert rows[0]["battery_level"] == 60


def test_renaming_after_setup_does_not_touch_setup_state(app):
    """Renaming from Settings must not push the user back into onboarding."""
    asyncio.run(app.setup_finish())
    select(app, ("aabbcc112233", "Front Door", True))
    assert asyncio.run(app.setup_state())["complete"] is True


def test_a_camera_can_be_renamed_repeatedly(app):
    select(app, ("aabbcc112233", "Front Door", True))
    select(app, ("aabbcc112233", "Side Gate", True))
    select(app, ("aabbcc112233", "Haustür", True))
    assert app.go2rtc_streams() == {"haustur": "aabbcc112233"}
    assert app.load_settings()["camera_names"]["aabbcc112233"] == "Haustür"
