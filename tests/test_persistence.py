"""Event and snapshot persistence, and the recorder's failure handling."""

import json


# ── Events ────────────────────────────────────────────────────────────────────

def test_events_survive_a_restart(app, mqtt_handler):
    """The feed was memory-only, so every container update emptied it."""
    mqtt_handler("ring/loc/camera/cam1/motion/state", "ON")
    assert app.EVENTS_FILE.exists()

    app.events.clear()
    app.load_events()

    assert len(app.events) == 1
    assert app.events[0]["device_id"] == "cam1"


def test_the_stored_feed_is_capped(app, mqtt_handler):
    for i in range(app.MAX_EVENTS + 25):
        mqtt_handler(f"ring/loc/camera/cam{i}/motion/state", "ON")
    assert len(json.loads(app.EVENTS_FILE.read_text())) == app.MAX_EVENTS


def test_a_corrupt_event_file_is_ignored(app):
    app.EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    app.EVENTS_FILE.write_text("{not json")
    app.load_events()
    assert app.events == []


def test_loading_events_without_a_file_is_harmless(app):
    app.load_events()
    assert app.events == []


# ── Snapshots ─────────────────────────────────────────────────────────────────

def test_snapshots_survive_a_restart(app, mqtt_handler):
    """Thumbnails 404'd after a restart until MQTT happened to republish."""
    jpeg = b"\xff\xd8\xff\xe0 image data"
    mqtt_handler("ring/loc/camera/cam1/snapshot/image", jpeg)

    app.snapshots.clear()
    app.load_snapshots()

    assert app.snapshots["cam1"] == jpeg


def test_a_newer_snapshot_replaces_the_stored_one(app, mqtt_handler):
    mqtt_handler("ring/loc/camera/cam1/snapshot/image", b"\xff\xd8old")
    mqtt_handler("ring/loc/camera/cam1/snapshot/image", b"\xff\xd8new")

    app.snapshots.clear()
    app.load_snapshots()

    assert app.snapshots["cam1"] == b"\xff\xd8new"


# ── Forgetting a device ───────────────────────────────────────────────────────

def test_disabling_a_camera_clears_its_state(app, mqtt_handler):
    mqtt_handler("ring/loc/camera/cam1/info/state", json.dumps({"batteryLevel": 10}))
    mqtt_handler("ring/loc/camera/cam1/snapshot/image", b"\xff\xd8jpeg")
    mqtt_handler("ring/loc/camera/cam1/status", "offline")
    assert "cam1" in app.device_states

    app.forget_device("cam1")

    assert "cam1" not in app.device_states
    assert "cam1" not in app.snapshots
    assert "cam1" not in app._device_availability
    assert "cam1" not in app._low_battery_notified
    assert not (app.SNAPSHOT_DIR / "cam1.jpg").exists()
