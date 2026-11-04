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
from urllib.parse import quote

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
    """Read livestream credentials from ring-mqtt config (preferred) or env vars.

    ring-mqtt owns these credentials and runs its RTSP server unauthenticated
    when they are unset — they are not the Ring account login.
    """
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
    """Build the RTSP URL, percent-encoding the credentials.

    An unescaped '@' (as in an email address) or ':' in the userinfo yields a
    URL ffmpeg cannot parse.
    """
    user, passwd = rtsp_credentials()
    userinfo = f"{quote(user, safe='')}:{quote(passwd, safe='')}@" if user or passwd else ""
    return f"rtsp://{userinfo}{RTSP_HOST}:{RTSP_PORT}/{device_id}_live"


RECORD_ATTEMPTS = 3
RETRY_DELAY     = 4                       # Ring needs a moment to bring the stream up
MIN_CLIP_BYTES  = 32 * 1024               # smaller than this is not real video
MIN_FREE_BYTES  = 512 * 1024 * 1024       # refuse to fill the disk completely


def free_bytes(path: Path) -> int:
    """Free space on the recordings volume, or -1 if it cannot be determined."""
    try:
        stat = os.statvfs(path)
        return stat.f_bavail * stat.f_frsize
    except OSError:
        return -1


def run_ffmpeg(device_id: str, out: Path, duration: int) -> tuple[bool, str]:
    """Record one clip. Returns (ok, reason) — the reason is empty on success."""
    cmd = [
        "ffmpeg", "-loglevel", "warning",
        "-rtsp_transport", "tcp",
        "-timeout", "15000000",           # give up on a dead RTSP socket
        "-i", rtsp_url(device_id),
        "-t", str(duration),
        "-c", "copy",
        "-y", str(out),
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except Exception as exc:
        return False, f"could not start ffmpeg: {exc}"

    with _lock:
        _active[device_id] = proc
    try:
        # Wall-clock bound: -t alone does not save us if the input never opens.
        _, stderr = proc.communicate(timeout=duration + 30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return False, "ffmpeg overran its time limit and was killed"
    finally:
        with _lock:
            _active.pop(device_id, None)

    if proc.returncode != 0:
        detail = (stderr or b"").decode(errors="replace").strip().splitlines()
        return False, (detail[-1] if detail else f"exit code {proc.returncode}")

    # A zero-exit ffmpeg can still leave an empty file when the stream drops
    # immediately — that used to be logged as "saved".
    if not out.exists():
        return False, "ffmpeg wrote no file"
    if out.stat().st_size < MIN_CLIP_BYTES:
        out.unlink(missing_ok=True)
        return False, "clip was empty"
    return True, ""


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

    free = free_bytes(VIDEO_PATH)
    if 0 <= free < MIN_FREE_BYTES:
        print(f"[{device_id}] only {free // 1024 // 1024} MB free — not recording")
        return

    # Local time, so filenames line up with what the dashboard shows. Set TZ on
    # the container; without it a container clock is UTC.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = cam_dir / f"{ts}_{kind}.mp4"

    print(f"[{device_id}] {kind} → recording {out.name} ({duration}s)")

    def run() -> None:
        for attempt in range(1, RECORD_ATTEMPTS + 1):
            ok, reason = run_ffmpeg(device_id, out, duration)
            if ok:
                # Defensive: a retention sweep or an external tool could have
                # removed it already, and this runs on a daemon thread where an
                # exception would vanish.
                size = out.stat().st_size // 1024 if out.exists() else 0
                print(f"[{device_id}] saved {out.name} ({size} KB)")
                return
            if attempt < RECORD_ATTEMPTS:
                print(f"[{device_id}] attempt {attempt} failed ({reason}) — retrying")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[{device_id}] giving up after {RECORD_ATTEMPTS} attempts: {reason}")

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
