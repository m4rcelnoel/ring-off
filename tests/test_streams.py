"""RTSP URL construction, go2rtc config handling and camera auto-discovery."""


# ── RTSP URLs ─────────────────────────────────────────────────────────────────

def test_no_credentials_produces_no_userinfo(app):
    """ring-mqtt runs its RTSP server unauthenticated unless configured."""
    assert app.rtsp_url("abc123") == "rtsp://ring-mqtt:8554/abc123_live"


def test_ring_mqtt_credentials_are_used_and_encoded(app, ring_config):
    ring_config(livestream_user="ring/user", livestream_pass="p@ss:w0rd!")
    assert app.rtsp_url("abc123") == (
        "rtsp://ring%2Fuser:p%40ss%3Aw0rd%21@ring-mqtt:8554/abc123_live"
    )


def test_env_fallback_encodes_the_at_sign(app, monkeypatch):
    """An unescaped '@' put a second one in the URL, making it unparseable."""
    monkeypatch.setattr(app, "RTSP_USER", "me@example.com")
    monkeypatch.setattr(app, "RTSP_PASS", "hunter2")
    assert app.rtsp_url("abc123") == (
        "rtsp://me%40example.com:hunter2@ring-mqtt:8554/abc123_live"
    )


def test_go2rtc_host_can_differ_from_the_webapp_host(app, monkeypatch):
    """go2rtc resolves the URL inside its own container, not in this process."""
    monkeypatch.setattr(app, "RTSP_HOST", "localhost")
    assert app.rtsp_url("abc") == "rtsp://localhost:8554/abc_live"
    assert app.rtsp_url("abc", "ring-mqtt") == "rtsp://ring-mqtt:8554/abc_live"


# ── go2rtc config ─────────────────────────────────────────────────────────────

def test_config_is_created_when_missing(app):
    """A file bind-mount over a missing file makes Docker create a directory."""
    assert not app.GO2RTC_CONFIG.exists()
    app.ensure_go2rtc_config()
    assert app.GO2RTC_CONFIG.exists()
    assert app.go2rtc_streams() == {}


def test_created_config_leaves_8555_to_webrtc(app):
    """`rtsp: listen: ':8555'` collides with go2rtc's WebRTC port."""
    app.ensure_go2rtc_config()
    text = app.GO2RTC_CONFIG.read_text()
    assert "webrtc:" in text
    assert "rtsp:" not in text


def test_streams_are_parsed_from_the_config(app):
    app.GO2RTC_CONFIG.parent.mkdir(parents=True)
    app.GO2RTC_CONFIG.write_text(
        "streams:\n  front_door: rtsp://ring-mqtt:8554/aabbcc_live\n"
    )
    assert app.go2rtc_streams() == {"front_door": "aabbcc"}


def test_placeholder_urls_are_repaired(app, ring_config):
    """Pre-1.2.6 configs hold ${RTSP_USER} that go2rtc no longer receives."""
    ring_config(livestream_user="u", livestream_pass="p")
    app.GO2RTC_CONFIG.parent.mkdir(parents=True)
    app.GO2RTC_CONFIG.write_text(
        "streams:\n"
        "  front_door: rtsp://${RTSP_USER}:${RTSP_PASS}@ring-mqtt:8554/aabbcc_live\n"
        "  # back_door: commented out\n"
    )
    app.sync_go2rtc_credentials()
    text = app.GO2RTC_CONFIG.read_text()

    assert "rtsp://u:p@ring-mqtt:8554/aabbcc_live" in text
    assert "${RTSP_USER}" not in text
    assert "# back_door: commented out" in text, "comments must survive the rewrite"
    assert app.go2rtc_streams() == {"front_door": "aabbcc"}


def test_wrong_host_is_corrected(app, monkeypatch):
    """A backend running outside Docker writes a host go2rtc cannot resolve.

    The match pattern is rebuilt per call, so a host change takes effect
    without reimporting the module.
    """
    monkeypatch.setattr(app, "RTSP_HOST", "localhost")
    app.GO2RTC_CONFIG.parent.mkdir(parents=True)
    app.GO2RTC_CONFIG.write_text(
        "streams:\n  cam: rtsp://localhost:8554/aabbcc_live\n"
    )
    app.sync_go2rtc_credentials()
    assert "rtsp://ring-mqtt:8554/aabbcc_live" in app.GO2RTC_CONFIG.read_text()


def test_foreign_streams_are_left_alone(app):
    """Hand-added streams pointing elsewhere must not be rewritten."""
    app.GO2RTC_CONFIG.parent.mkdir(parents=True)
    app.GO2RTC_CONFIG.write_text(
        "streams:\n  garage: rtsp://192.168.1.50:554/some_live\n"
    )
    app.sync_go2rtc_credentials()
    assert "rtsp://192.168.1.50:554/some_live" in app.GO2RTC_CONFIG.read_text()


# ── Auto-discovery ────────────────────────────────────────────────────────────

def test_new_camera_is_added(app):
    app._check_auto_discovery("ddeeff112233")
    assert app.go2rtc_streams() == {"camera_112233": "ddeeff112233"}
    assert "${RTSP_USER}" not in app.GO2RTC_CONFIG.read_text()


def test_known_camera_is_not_added_twice(app):
    app._check_auto_discovery("ddeeff112233")
    before = app.GO2RTC_CONFIG.read_text()
    app._discovered_devices.clear()          # forget the in-memory shortcut
    app._check_auto_discovery("ddeeff112233")
    assert app.GO2RTC_CONFIG.read_text() == before


def test_api_success_avoids_a_container_restart(app, monkeypatch):
    """Restarting go2rtc drops everyone currently watching a stream."""
    restarts = []
    monkeypatch.setattr(app, "restart_go2rtc", lambda: restarts.append(1))
    monkeypatch.setattr(app, "_go2rtc_put_stream", lambda name, src: True)
    app._check_auto_discovery("aabbccddeeff")
    assert restarts == []


def test_restart_is_the_fallback_when_the_api_fails(app, monkeypatch):
    import threading
    restarts = []
    monkeypatch.setattr(app, "restart_go2rtc", lambda: restarts.append(1))
    monkeypatch.setattr(app, "_go2rtc_put_stream", lambda name, src: False)
    app._check_auto_discovery("aabbccddeeff")
    for t in threading.enumerate():          # discovery restarts on a thread
        if t is not threading.current_thread():
            t.join(timeout=2)
    assert restarts == [1]
