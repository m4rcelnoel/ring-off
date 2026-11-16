"""Waking slow battery cameras before go2rtc asks for their stream.

go2rtc gives ring-mqtt 5 s to answer DESCRIBE; a waking battery doorbell
needs over 20 s. The webapp therefore holds its own RTSP session open first.
"""

import asyncio
import json
import threading
import time

import pytest


class FakeRingMqtt:
    """An RTSP server that answers DESCRIBE after `delay` and records traffic."""

    def __init__(self, delay=0.0, status="200 OK"):
        self.delay, self.status = delay, status
        self.requests: list[str] = []
        self.connected = threading.Event()
        self.closed = threading.Event()
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()

        async def handle(reader, writer):
            self.connected.set()
            try:
                while line := await reader.readline():
                    if line.strip() and b"RTSP/1.0" in line:
                        self.requests.append(line.decode())
                        while (await reader.readline()).strip():
                            pass      # headers
                        if line.startswith(b"DESCRIBE"):
                            # Like ring-mqtt: wait for the camera, but notice
                            # a client that hangs up in the meantime.
                            hangup = asyncio.ensure_future(reader.read(1))
                            done, _ = await asyncio.wait({hangup}, timeout=self.delay)
                            if hangup in done and not hangup.result():
                                return
                            hangup.cancel()
                            await asyncio.gather(hangup, return_exceptions=True)
                        writer.write(f"RTSP/1.0 {self.status}\r\nCSeq: 1\r\n\r\n".encode())
                        await writer.drain()
            except Exception:
                pass
            finally:
                self.closed.set()

        async def start():
            self.server = await asyncio.start_server(handle, "127.0.0.1", 0)
            self.port = self.server.sockets[0].getsockname()[1]
            ready.set()

        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        asyncio.run_coroutine_threadsafe(start(), self.loop)
        ready.wait(5)

    def stop(self):
        # Stop the loop thread too: other tests join every running thread.
        self.loop.call_soon_threadsafe(self.server.close)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(2)


@pytest.fixture
def ring_mqtt(app, monkeypatch):
    servers = []

    def make(**kw):
        server = FakeRingMqtt(**kw)
        servers.append(server)
        monkeypatch.setattr(app, "RTSP_HOST", "127.0.0.1")
        monkeypatch.setattr(app, "RTSP_PORT", str(server.port))
        monkeypatch.setattr(app.RtspHold, "KEEPALIVE_INTERVAL", 0.05)
        return server

    yield make
    for server in servers:
        server.stop()


def test_hold_waits_for_a_slow_camera_and_keeps_it_awake(app, ring_mqtt):
    camera = ring_mqtt(delay=0.5)

    async def run():
        hold = app.RtspHold("abc")
        started = time.monotonic()
        assert await hold.open() is True
        waited = time.monotonic() - started
        await asyncio.sleep(0.3)               # several keepalive periods
        hold.close()
        return waited

    waited = asyncio.run(run())
    assert waited >= 0.5
    assert camera.requests[0].startswith("DESCRIBE rtsp://127.0.0.1:")
    assert "/abc_live RTSP/1.0" in camera.requests[0]
    assert sum(r.startswith("OPTIONS") for r in camera.requests) >= 3
    assert camera.closed.wait(2), "closing the hold must end the session"


def test_hold_reports_a_camera_that_does_not_come_up(app, ring_mqtt):
    ring_mqtt(status="404 Not Found")
    assert asyncio.run(app.RtspHold("abc").open()) is False


def test_hold_sends_ring_mqtt_credentials(app, ring_mqtt, ring_config):
    camera = ring_mqtt()
    ring_config(livestream_user="viewer", livestream_pass="p@ss")

    async def run():
        hold = app.RtspHold("abc")
        await hold.open()
        hold.close()

    asyncio.run(run())
    assert camera.requests, "no DESCRIBE received"


def _streams(app):
    app.GO2RTC_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    app.GO2RTC_CONFIG.write_text("streams:\n  front: rtsp://ring-mqtt:8554/abc_live\n")


class FakeGo2rtc:
    connected_at: list = []

    def __init__(self, url):
        FakeGo2rtc.connected_at.append(time.monotonic())
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def send(self, message):
        self.sent.append(message)

    def __aiter__(self):
        return self._messages()

    async def _messages(self):
        while not self.sent:
            await asyncio.sleep(0.01)
        yield json.dumps({"type": "webrtc/answer", "value": "v=0"})
        await asyncio.Event().wait()


def test_proxy_asks_go2rtc_only_once_the_camera_is_awake(app, ring_mqtt, monkeypatch):
    from fastapi.testclient import TestClient
    _streams(app)
    ring_mqtt(delay=0.5)
    FakeGo2rtc.connected_at = []
    monkeypatch.setattr(app.ws_lib, "connect", FakeGo2rtc)

    with TestClient(app.app).websocket_connect("/ws/video?src=front") as ws:
        sent = time.monotonic()
        ws.send_text(json.dumps({"type": "webrtc/offer", "value": "v=0"}))
        assert ws.receive_json()["type"] == "webrtc/answer"

    assert FakeGo2rtc.connected_at[0] - sent >= 0.45, "go2rtc was asked before the camera woke"


def test_leaving_while_the_camera_wakes_stops_waking_it(app, ring_mqtt, monkeypatch):
    from fastapi.testclient import TestClient
    _streams(app)
    camera = ring_mqtt(delay=5)
    FakeGo2rtc.connected_at = []
    monkeypatch.setattr(app.ws_lib, "connect", FakeGo2rtc)

    with TestClient(app.app).websocket_connect("/ws/video?src=front"):
        assert camera.connected.wait(2)
    assert camera.closed.wait(2), "the RTSP session must close when the viewer leaves"
    assert FakeGo2rtc.connected_at == [], "go2rtc must not be asked after the viewer left"
