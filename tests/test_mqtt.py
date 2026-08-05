"""MQTT topic handling and the WebSocket broadcast it feeds."""

import asyncio
import json


# ── Event topics ──────────────────────────────────────────────────────────────

def test_motion_event_is_recorded(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc123/motion/state", "ON")
    assert len(app.events) == 1
    event = app.events[0]
    assert event["kind"] == "motion"
    assert event["device_id"] == "abc123"
    assert event["location_id"] == "loc1"
    assert event["person_detected"] is False


def test_ding_event_is_recorded(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc123/ding/state", "ON")
    assert app.events[0]["kind"] == "ding"


def test_off_state_is_not_an_event(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc123/motion/state", "OFF")
    assert app.events == []


def test_person_detection_is_read_from_attributes(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc123/motion/attributes",
                 json.dumps({"personDetected": True}))
    mqtt_handler("ring/loc1/camera/abc123/motion/state", "ON")
    assert app.events[0]["person_detected"] is True


def test_a_ding_is_never_marked_as_a_person(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc123/motion/attributes",
                 json.dumps({"personDetected": True}))
    mqtt_handler("ring/loc1/camera/abc123/ding/state", "ON")
    assert app.events[0]["person_detected"] is False


def test_event_history_is_capped(app, mqtt_handler):
    for i in range(120):
        mqtt_handler(f"ring/loc1/camera/cam{i}/motion/state", "ON")
    assert len(app.events) == 100


def test_newest_event_is_first(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/first/motion/state", "ON")
    mqtt_handler("ring/loc1/camera/second/motion/state", "ON")
    assert app.events[0]["device_id"] == "second"


# ── Device state ──────────────────────────────────────────────────────────────

def test_info_state_populates_device_state(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc123/info/state", json.dumps({
        "batteryLevel": 82, "wirelessSignal": -55,
        "wirelessNetwork": "wifi", "firmwareStatus": "Up to Date",
    }))
    state = app.device_states["abc123"]
    assert state["battery_level"] == 82
    assert state["wifi_signal"] == -55
    assert state["type"] == "camera"


def test_cameras_are_discovered_from_info_alone(app, mqtt_handler):
    """Discovery used to run only on motion, so cameras never appeared idle."""
    mqtt_handler("ring/loc1/camera/abc123/info/state", json.dumps({"batteryLevel": 50}))
    assert app.go2rtc_streams() == {"camera_abc123": "abc123"}


def test_chimes_are_not_added_as_streams(app, mqtt_handler):
    mqtt_handler("ring/loc1/chime/ch1/info/state", json.dumps({"wirelessSignal": -40}))
    assert app.device_states["ch1"]["type"] == "chime"
    assert app.go2rtc_streams() == {}


def test_snapshot_payload_is_kept_as_bytes(app, mqtt_handler):
    """Decoding a JPEG as text would corrupt it."""
    jpeg = b"\xff\xd8\xff\xe0 not text \x00\x01"
    mqtt_handler("ring/loc1/camera/abc123/snapshot/image", jpeg)
    assert app.snapshots["abc123"] == jpeg


def test_availability_is_tracked(app, mqtt_handler):
    """ring-mqtt publishes availability to `${deviceTopic}/status` — five
    segments ending in "status". Matching "availability" over six segments
    meant the connection-lost alert never fired once."""
    mqtt_handler("ring/loc1/camera/abc123/status", "offline")
    assert app._device_availability["abc123"] == "offline"


def test_going_offline_is_reported_once(app, mqtt_handler):
    alerts = []
    app.send_device_alert = lambda *a: alerts.append(a)   # schedule() closes it
    mqtt_handler("ring/loc1/camera/abc123/status", "offline")
    mqtt_handler("ring/loc1/camera/abc123/status", "offline")
    assert app._device_availability["abc123"] == "offline"


def test_coming_back_online_is_tracked(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc123/status", "offline")
    mqtt_handler("ring/loc1/camera/abc123/status", "online")
    assert app._device_availability["abc123"] == "online"


def test_low_battery_alerts_only_once(app, mqtt_handler):
    for _ in range(3):
        mqtt_handler("ring/loc1/camera/abc123/info/state",
                     json.dumps({"batteryLevel": 5}))
    assert app._low_battery_notified == {"abc123"}


def test_low_battery_rearms_after_recovery(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc/info/state", json.dumps({"batteryLevel": 5}))
    mqtt_handler("ring/loc1/camera/abc/info/state", json.dumps({"batteryLevel": 90}))
    assert app._low_battery_notified == set()


def test_malformed_payload_does_not_raise(app, mqtt_handler):
    mqtt_handler("ring/loc1/camera/abc123/info/state", "{not json")


# ── Broadcast ─────────────────────────────────────────────────────────────────

class FakeWS:
    def __init__(self, alive=True):
        self.alive, self.sent = alive, []

    async def send_json(self, message):
        if not self.alive:
            raise RuntimeError("closed")
        self.sent.append(message)


def test_broadcast_delivers_and_prunes(app):
    """`ws_clients -= dead` made the name function-local: UnboundLocalError
    on every call, swallowed by an unawaited future, so no live event ever
    reached a browser."""
    live, dead = FakeWS(), FakeWS(alive=False)
    app.ws_clients.update({live, dead})

    asyncio.run(app.broadcast({"type": "event", "data": {"id": "x"}}))

    assert live.sent == [{"type": "event", "data": {"id": "x"}}]
    assert app.ws_clients == {live}


def test_schedule_without_a_loop_is_safe(app):
    app.schedule(app.broadcast({"type": "noop"}))


def test_schedule_reports_failures(app, capsys):
    async def boom():
        raise ValueError("boom")

    async def drive():
        app._loop = asyncio.get_running_loop()
        app.schedule(boom())
        await asyncio.sleep(0.05)

    asyncio.run(drive())
    app._loop = None
    assert "Background task failed" in capsys.readouterr().out
