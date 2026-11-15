"""Regressions for the auth gaps and file handling fixed after 1.3.0."""

import asyncio
import json

import pytest
from starlette.websockets import WebSocketDisconnect


def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app.app)      # no context manager: skips lifespan/MQTT


def lock(app):
    asyncio.run(app.set_password(app.SetPasswordRequest(password="hunter2")))


# ── WebSockets bypass BaseHTTPMiddleware, so they check auth themselves ───────

@pytest.mark.parametrize("path", ["/ws/events", "/ws/video?src=front"])
def test_websockets_are_refused_without_a_session(app, path):
    lock(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client(app).websocket_connect(path) as ws:
            ws.receive_json()
    assert exc.value.code == 1008


def test_events_websocket_works_with_a_session(app):
    lock(app)
    session = client(app)
    session.post("/api/app/login", json={"password": "hunter2"})
    with session.websocket_connect("/ws/events") as ws:
        assert ws.receive_json()["type"] == "history"


def test_events_websocket_is_open_without_a_password(app):
    with client(app).websocket_connect("/ws/events") as ws:
        assert ws.receive_json()["type"] == "history"


def test_video_proxy_encodes_the_source(app, monkeypatch):
    seen = []

    class Refuse:
        def __init__(self, url):
            seen.append(url)
        async def __aenter__(self):
            raise OSError("no go2rtc in tests")
        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(app.ws_lib, "connect", Refuse)
    with client(app).websocket_connect("/ws/video?src=a%26b%3Dc") as ws:
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    assert seen == [f"{app.GO2RTC_WS}/api/ws?src=a%26b%3Dc"]


# ── go2rtc proxy ─────────────────────────────────────────────────────────────

def test_go2rtc_proxy_requires_a_session(app):
    lock(app)
    assert client(app).get("/proxy/go2rtc/video-rtc.js").status_code == 401


@pytest.mark.parametrize("path", ["api/config", "api/streams", "../api/config", "video-rtc.js/x"])
def test_go2rtc_proxy_only_serves_player_scripts(app, path):
    assert client(app).get(f"/proxy/go2rtc/{path}").status_code == 404


def test_go2rtc_proxy_refuses_writes(app):
    assert client(app).post("/proxy/go2rtc/api/streams?name=x&src=exec:id").status_code == 405


# ── Recordings ───────────────────────────────────────────────────────────────

@pytest.fixture
def clip(app):
    folder = app.VIDEO_PATH / "cam"
    folder.mkdir(parents=True)
    path = folder / "20260101_120000_motion.mp4"
    path.write_bytes(b"x" * 100)
    return path


def test_a_range_past_the_end_is_unsatisfiable(app, clip):
    r = client(app).get(f"/recordings/files/cam/{clip.name}", headers={"range": "bytes=500-"})
    assert r.status_code == 416
    assert r.headers["content-range"] == "bytes */100"


def test_a_valid_range_still_works(app, clip):
    r = client(app).get(f"/recordings/files/cam/{clip.name}", headers={"range": "bytes=10-19"})
    assert r.status_code == 206
    assert r.content == b"x" * 10


def test_only_clips_can_be_deleted(app, clip):
    other = clip.parent / "notes.txt"
    other.write_text("keep me")
    assert client(app).delete("/api/recordings/cam/notes.txt").status_code == 404
    assert other.exists()


def test_a_clip_can_be_deleted(app, clip):
    assert client(app).delete(f"/api/recordings/cam/{clip.name}").status_code == 200
    assert not clip.exists()


def test_the_video_root_itself_is_off_limits(app):
    app.VIDEO_PATH.mkdir(parents=True)
    (app.VIDEO_PATH / "x.mp4").write_bytes(b"x")
    assert client(app).delete("/api/recordings/./x.mp4").status_code in (400, 404)
    assert (app.VIDEO_PATH / "x.mp4").exists()


# ── Settings file ────────────────────────────────────────────────────────────

def test_settings_are_written_atomically(app):
    app.save_settings({**app.SETTINGS_DEFAULTS, "record_motion": False})
    assert json.loads(app.SETTINGS_FILE.read_text())["record_motion"] is False
    assert [p.name for p in app.SETTINGS_FILE.parent.iterdir()] == ["settings.json"]


def test_a_corrupt_settings_file_does_not_break_startup(app):
    app.SETTINGS_FILE.parent.mkdir(parents=True)
    app.SETTINGS_FILE.write_text("{not json")
    app.adopt_existing_install()      # must not raise
