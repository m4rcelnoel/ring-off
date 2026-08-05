"""Shared fixtures.

`main.py` and `recorder.py` read their configuration into module-level
constants at import time, so tests redirect those constants at runtime rather
than relying on the environment.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))
sys.path.insert(0, str(ROOT / "recorder"))


@pytest.fixture
def app(tmp_path, monkeypatch):
    """The webapp module with every path pointed at a scratch directory."""
    import main

    monkeypatch.setattr(main, "GO2RTC_CONFIG", tmp_path / "config" / "go2rtc.yaml")
    monkeypatch.setattr(main, "RING_MQTT_CONFIG", tmp_path / "ring" / "config.json")
    monkeypatch.setattr(main, "RING_MQTT_STATE", tmp_path / "ring" / "ring-state.json")
    monkeypatch.setattr(main, "SETTINGS_FILE", tmp_path / "webapp" / "settings.json")
    monkeypatch.setattr(main, "VIDEO_PATH", tmp_path / "videos")
    monkeypatch.setattr(main, "RTSP_USER", "")
    monkeypatch.setattr(main, "RTSP_PASS", "")

    # Never touch the network or a real go2rtc from a test.
    monkeypatch.setattr(main, "_go2rtc_put_stream", lambda name, src: True)
    monkeypatch.setattr(main, "restart_go2rtc", lambda: None)
    monkeypatch.setattr(main, "restart_ring_mqtt", lambda: None)

    main.events.clear()
    main.device_states.clear()
    main.snapshots.clear()
    main.motion_attrs.clear()
    main.ws_clients.clear()
    main.app_sessions.clear()
    main._discovered_devices.clear()
    main._low_battery_notified.clear()
    main._device_availability.clear()
    main._loop = None

    return main


@pytest.fixture
def ring_config(app):
    """Writes ring-mqtt's config.json, creating the directory."""
    def write(**values):
        app.RING_MQTT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        import json
        app.RING_MQTT_CONFIG.write_text(json.dumps(values))
    return write


@pytest.fixture
def mqtt_handler(app, monkeypatch):
    """The on_message callback from setup_mqtt, without a broker connection."""
    import paho.mqtt.client as mqtt

    def refuse(self, *a, **kw):
        raise OSError("no broker in tests")

    monkeypatch.setattr(mqtt.Client, "connect", refuse)
    client = app.setup_mqtt()

    class Msg:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload if isinstance(payload, bytes) else payload.encode()

    def deliver(topic, payload):
        client.on_message(client, None, Msg(topic, payload))

    return deliver
