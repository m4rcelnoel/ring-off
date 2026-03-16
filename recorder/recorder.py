"""
recorder.py — records Ring RTSP streams to disk on motion/ding events.

Settings are read from a shared JSON file (written by the webapp) on each event,
so changes take effect immediately without restarting the container.
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

MQTT_HOST       = os.getenv("MQTT_HOST",  "mosquitto")
MQTT_PORT       = int(os.getenv("MQTT_PORT", 1883))
RTSP_HOST       = os.getenv("RTSP_HOST",  "ring-mqtt")
RTSP_PORT       = int(os.getenv("RTSP_PORT", 8554))
RTSP_USER_ENV   = os.getenv("RTSP_USER",  "")
RTSP_PASS_ENV   = os.getenv("RTSP_PASS",  "")
RING_MQTT_CONFIG = Path(os.getenv("RING_MQTT_CONFIG", "/ring-mqtt-data/config.json"))
VIDEO_PATH      = Path(os.getenv("VIDEO_PATH", "/videos"))
SETTINGS_FILE   = Path(os.getenv("SETTINGS_FILE", "/app/data/settings.json"))


def rtsp_credentials() -> tuple[str, str]:
    """Read livestream credentials from ring-mqtt config (preferred) or env vars."""
    if RING_MQTT_CONFIG.exists():
        try:
            cfg = json.loads(RING_MQTT_CONFIG.read_text())
            user = cfg.get("livestream_user", "")
            passwd = cfg.get("livestream_pass", "")
            if user and passwd:
                return user, passwd
        except Exception:
            pass
    return RTSP_USER_ENV, RTSP_PASS_ENV


# Track active recordings per device to avoid duplicates
_active: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


def load_settings() -> dict:
    defaults = {
        "record_motion": True,
        "record_ding": True,
        "record_duration": 60,
        "retention_days": 30,
    }
    try:
        if SETTINGS_FILE.exists():
            return {**defaults, **json.loads(SETTINGS_FILE.read_text())}
    except Exception:
        pass
    return defaults


def rtsp_url(device_id: str) -> str:
    user, passwd = rtsp_credentials()
    return f"rtsp://{user}:{passwd}@{RTSP_HOST}:{RTSP_PORT}/{device_id}_live"


def record(device_id: str, kind: str) -> None:
    settings = load_settings()

    if kind == "motion" and not settings.get("record_motion", True):
        print(f"[{device_id}] motion recording disabled, skipping")
        return
    if kind == "ding" and not settings.get("record_ding", True):
        print(f"[{device_id}] ding recording disabled, skipping")
        return

    duration = int(settings.get("record_duration", 60))

    with _lock:
        proc = _active.get(device_id)
        if proc and proc.poll() is None:
            print(f"[{device_id}] already recording, skipping")
            return

    cam_dir = VIDEO_PATH / device_id
    cam_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = cam_dir / f"{ts}_{kind}.mp4"

    cmd = [
        "ffmpeg", "-loglevel", "warning",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url(device_id),
        "-t", str(duration),
        "-c", "copy",
        str(out),
    ]

    print(f"[{device_id}] {kind} → recording {out.name} ({duration}s)")

    def run() -> None:
        try:
            proc = subprocess.Popen(cmd)
            with _lock:
                _active[device_id] = proc
            proc.wait()
            print(f"[{device_id}] saved {out.name}")
        except Exception as exc:
            print(f"[{device_id}] ffmpeg error: {exc}")
        finally:
            with _lock:
                _active.pop(device_id, None)

    threading.Thread(target=run, daemon=True).start()


def cleanup_old_recordings() -> None:
    """Background thread: delete clips older than retention_days."""
    while True:
        time.sleep(3600)  # check hourly
        try:
            settings = load_settings()
            retention_days = int(settings.get("retention_days", 30))
            if retention_days <= 0:
                continue
            cutoff = time.time() - (retention_days * 86400)
            deleted = 0
            for device_dir in VIDEO_PATH.iterdir():
                if not device_dir.is_dir():
                    continue
                for clip in device_dir.glob("*.mp4"):
                    if clip.stat().st_mtime < cutoff:
                        clip.unlink()
                        deleted += 1
            if deleted:
                print(f"Retention cleanup: deleted {deleted} clips older than {retention_days} days")
        except Exception as e:
            print(f"Retention cleanup error: {e}")


def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties=None) -> None:
    print(f"MQTT connected (rc={reason_code})")
    client.subscribe("ring/+/camera/+/motion/state")
    client.subscribe("ring/+/camera/+/ding/state")


def on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
    if msg.payload.decode().strip() != "ON":
        return
    # ring/<loc>/camera/<device_id>/motion|ding/state
    parts = msg.topic.split("/")
    if len(parts) < 6:
        return
    record(device_id=parts[3], kind=parts[4])


def main() -> None:
    VIDEO_PATH.mkdir(parents=True, exist_ok=True)
    print(f"Recorder starting — saving to {VIDEO_PATH}")
    print(f"RTSP: {RTSP_HOST}:{RTSP_PORT}  |  settings: {SETTINGS_FILE}")

    threading.Thread(target=cleanup_old_recordings, daemon=True).start()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
