"""
Ring Off — Web App Backend
FastAPI server providing:
- Ring OAuth authentication (with 2FA)
- Real-time event WebSocket
- go2rtc HTTP + WebSocket proxy (camera streams)
- Home Assistant REST API proxy
- Settings persistence
- Snapshot preview (MQTT binary JPEG)
- Person detection (motion/attributes)
- Recordings browser API
- Auto-discovery of Ring cameras → go2rtc config
- Push notifications (ntfy.sh / Gotify / Pushover)
- App-level authentication (password + session cookie)
"""

import asyncio
import hashlib
import json
import os
import socket
import unicodedata
import re
import secrets
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import bcrypt
import yaml
import docker
import httpx
import websockets as ws_lib
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import paho.mqtt.client as mqtt
from ring_doorbell import Auth, Requires2FAError
from starlette.middleware.base import BaseHTTPMiddleware

# ── Config ────────────────────────────────────────────────────────────────────

RING_MQTT_CONFIG  = Path(os.getenv("RING_MQTT_CONFIG",  "/ring-mqtt-data/config.json"))
# ring-mqtt keeps the Ring refresh token in its state file, not in config.json.
RING_MQTT_STATE   = Path(os.getenv("RING_MQTT_STATE",
                                   str(RING_MQTT_CONFIG.parent / "ring-state.json")))
SETTINGS_FILE     = Path(os.getenv("SETTINGS_FILE",     "/app/data/settings.json"))
GO2RTC_URL        = os.getenv("GO2RTC_URL",             "http://go2rtc:1984")
GO2RTC_WS         = os.getenv("GO2RTC_WS_URL",          "ws://go2rtc:1984")
GO2RTC_CONFIG     = Path(os.getenv("GO2RTC_CONFIG",     "/config/go2rtc.yaml"))
GO2RTC_CONTAINER  = os.getenv("GO2RTC_CONTAINER",       "ring-go2rtc")
MQTT_HOST         = os.getenv("MQTT_HOST",              "mosquitto")
MQTT_PORT         = int(os.getenv("MQTT_PORT",          "1883"))
RING_CONTAINER    = os.getenv("RING_CONTAINER",         "ring-mqtt")
RTSP_HOST         = os.getenv("RTSP_HOST",              "ring-mqtt")
RTSP_PORT         = os.getenv("RTSP_PORT",              "8554")
# How go2rtc reaches ring-mqtt's RTSP server. go2rtc always runs in Docker, so
# this stays a service name even when the backend itself runs on the host for
# development and needs RTSP_HOST=localhost for its own ffmpeg pulls.
GO2RTC_RTSP_HOST  = os.getenv("GO2RTC_RTSP_HOST",       "ring-mqtt")
# ring-mqtt's internal RTSP server runs without authentication unless
# livestream_user/livestream_pass are set in its own config.json. These env vars
# are only a fallback for hand-configured setups — see _rtsp_credentials().
RTSP_USER         = os.getenv("RTSP_USER",              "")
RTSP_PASS         = os.getenv("RTSP_PASS",              "")
VIDEO_PATH        = Path(os.getenv("VIDEO_PATH",        "/videos"))
USER_AGENT        = "ring-off/1.1"

# ── In-memory state ───────────────────────────────────────────────────────────

events: list[dict]         = []
pending_auth: dict         = {}   # session_id → {auth, email, password}
ws_clients: set[WebSocket] = set()
device_states: dict        = {}   # device_id → device info
snapshots: dict[str, bytes]= {}   # device_id → latest JPEG bytes
motion_attrs: dict         = {}   # device_id → latest motion/attributes payload
app_sessions: set[str]     = set()  # active session tokens
_loop: asyncio.AbstractEventLoop | None = None
_low_battery_notified: set[str] = set()  # device_ids already alerted for low battery
_device_availability: dict[str, str] = {}  # device_id → "online"/"offline"
_mqtt_connected: bool = False

# ── Persistence helpers ───────────────────────────────────────────────────────

SETTINGS_DEFAULTS: dict = {
    "ha_url":                    "",
    "ha_token":                  "",
    "record_motion":             True,
    "record_ding":               True,
    "record_duration":           60,
    "retention_days":            30,
    "notify_url":                "",
    "notify_on_motion":          True,
    "notify_on_ding":            True,
    "notify_on_low_battery":     True,
    "low_battery_threshold":     20,
    "notify_on_connection_lost": True,
    "app_password_hash":         "",
    "setup_complete":            False,
    "camera_names":              {},   # device_id → friendly name
    "disabled_cameras":          [],   # device_ids the user chose not to show
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        return {**SETTINGS_DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
    return dict(SETTINGS_DEFAULTS)


def save_settings(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2))


def load_ring_config() -> dict:
    if RING_MQTT_CONFIG.exists():
        return json.loads(RING_MQTT_CONFIG.read_text())
    return {}


def load_ring_state() -> dict:
    if RING_MQTT_STATE.exists():
        try:
            return json.loads(RING_MQTT_STATE.read_text())
        except Exception:
            pass
    return {}


def ring_token_present() -> bool:
    """True once ring-mqtt has a refresh token it will actually use."""
    return bool(load_ring_state().get("ring_token")
                # Fallback for older ring-mqtt versions that read config.json.
                or load_ring_config().get("ring_token"))


def save_ring_token(refresh_token: str) -> None:
    """Persist the Ring refresh token where ring-mqtt actually reads it.

    ring-mqtt loads the token from ring-state.json (lib/state.js → lib/ring.js),
    not from config.json. Writing it to config.json leaves ring-mqtt
    unauthenticated while the dashboard believes setup succeeded — the login
    appears to work and no cameras ever appear.
    """
    state = load_ring_state()
    state["ring_token"] = refresh_token
    # ring-mqtt regenerates these if absent, but writing a complete file keeps
    # its own schema intact.
    state.setdefault("systemId", hashlib.sha256(secrets.token_bytes(32)).hexdigest())
    state.setdefault("devices", {})
    # In Docker this is a bind mount and always exists; outside it may not.
    RING_MQTT_STATE.parent.mkdir(parents=True, exist_ok=True)
    RING_MQTT_STATE.write_text(json.dumps(state))


def restart_ring_mqtt() -> None:
    try:
        client = docker.from_env()
        container = client.containers.get(RING_CONTAINER)
        container.restart()
        print("ring-mqtt restarted")
    except Exception as e:
        print(f"Could not restart ring-mqtt: {e}")


def restart_go2rtc() -> None:
    try:
        client = docker.from_env()
        container = client.containers.get(GO2RTC_CONTAINER)
        container.restart()
        print("go2rtc restarted")
    except Exception as e:
        print(f"Could not restart go2rtc: {e}")

# ── Background task scheduling ────────────────────────────────────────────────

def _log_task_error(future) -> None:
    try:
        future.result()
    except Exception as e:
        print(f"Background task failed: {e!r}")


def schedule(coro) -> None:
    """Run a coroutine on the main event loop from the MQTT thread.

    Failures are logged instead of vanishing into an unawaited future — an
    exception in here used to silently disable live event delivery entirely.
    """
    if _loop is None:
        coro.close()
        return
    asyncio.run_coroutine_threadsafe(coro, _loop).add_done_callback(_log_task_error)

# ── WebSocket broadcast ───────────────────────────────────────────────────────

async def broadcast(message: dict) -> None:
    dead: set[WebSocket] = set()
    for ws in ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    # difference_update, not `-=`: an augmented assignment would rebind
    # ws_clients as a function local and raise UnboundLocalError on the loop above.
    ws_clients.difference_update(dead)

# ── Push notifications ────────────────────────────────────────────────────────

async def post_notification(url: str, title: str, body: str) -> tuple[bool, str]:
    """Deliver one notification, reporting what actually happened.

    Gotify is detected by its /message path; anything else is treated as ntfy.
    Returns (ok, detail) so callers can surface a real HTTP status instead of
    failing silently into the log.
    """
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            if "/message" in url:
                resp = await client.post(
                    url, json={"title": title, "message": body, "priority": 5})
            else:
                resp = await client.post(
                    url, headers={"Title": title}, content=body.encode())
    except Exception as e:
        return False, f"Could not reach {url.split('/')[2] if '//' in url else url}: {e}"

    if resp.status_code < 300:
        return True, f"HTTP {resp.status_code}"
    return False, f"HTTP {resp.status_code} — {resp.text[:200]}"


async def send_notification(event: dict) -> None:
    """Send push notification for motion/ding events via ntfy.sh / Gotify."""
    settings = load_settings()
    notify_url = settings.get("notify_url", "").strip()
    if not notify_url:
        return
    kind = event.get("kind", "")
    if kind == "motion" and not settings.get("notify_on_motion", True):
        return
    if kind == "ding" and not settings.get("notify_on_ding", True):
        return

    device_id = event.get("device_id", "unknown")
    person = event.get("person_detected", False)

    if kind == "motion":
        title = "Person Detected" if person else "Motion Detected"
        body = f"{'Person' if person else 'Motion'} detected at camera {device_id}"
    else:
        title = "Doorbell"
        body = f"Doorbell rang at camera {device_id}"

    ok, detail = await post_notification(notify_url, title, body)
    if not ok:
        print(f"Notification failed: {detail}")


async def send_device_alert(title: str, body: str) -> None:
    """Send a push notification for device-health events (low battery, connection lost)."""
    notify_url = load_settings().get("notify_url", "").strip()
    if not notify_url:
        return
    ok, detail = await post_notification(notify_url, title, body)
    if not ok:
        print(f"Device alert failed: {detail}")

# ── RTSP credentials / URLs ───────────────────────────────────────────────────

def _rtsp_credentials() -> tuple[str, str]:
    """Credentials for ring-mqtt's internal RTSP server.

    ring-mqtt owns these: it stores them as livestream_user/livestream_pass in
    its own config.json, and runs the RTSP server without authentication when
    they are unset. RTSP_USER/RTSP_PASS remain only as a fallback for setups
    that configure ring-mqtt by hand. They are NOT the Ring account login.
    """
    cfg = load_ring_config()
    user   = cfg.get("livestream_user") or RTSP_USER
    passwd = cfg.get("livestream_pass") or RTSP_PASS
    return user, passwd


def rtsp_url(device_id: str, host: str | None = None) -> str:
    """Build the RTSP URL for a device, percent-encoding the credentials.

    `host` defaults to RTSP_HOST (how this process reaches ring-mqtt). Pass
    GO2RTC_RTSP_HOST for URLs written into go2rtc.yaml, which are resolved
    inside the go2rtc container rather than here.

    Encoding matters: an unescaped '@' (as in an email address) or ':' in the
    userinfo produces a URL that ffmpeg and go2rtc cannot parse at all.
    """
    user, passwd = _rtsp_credentials()
    userinfo = f"{quote(user, safe='')}:{quote(passwd, safe='')}@" if user or passwd else ""
    return f"rtsp://{userinfo}{host or RTSP_HOST}:{RTSP_PORT}/{device_id}_live"

# ── go2rtc config ─────────────────────────────────────────────────────────────

# No `rtsp:` override here on purpose. Setting it to :8555 (as earlier versions
# did) collides with go2rtc's default WebRTC port, so the WebRTC TCP listener
# never binds and browsers are left with only an unreachable container-IP UDP
# candidate — a permanently black player. go2rtc's own defaults are correct.
GO2RTC_DEFAULT_CONFIG = """api:
  listen: ':1984'

webrtc:
  listen: ':8555'

# Cameras are added here automatically as they are discovered via MQTT.
streams:
"""

# Matches a stream entry so the source URL can be rewritten in place, keeping
# the rest of the file (comments, formatting) untouched. Scoped to the hosts we
# generate ourselves, so hand-added streams pointing elsewhere are left alone —
# and so an entry written with the wrong one of the two gets corrected.
def _stream_line_pattern() -> re.Pattern:
    """Built on demand so it always reflects the current host settings."""
    hosts = "|".join(re.escape(h) for h in sorted({GO2RTC_RTSP_HOST, RTSP_HOST}))
    return re.compile(
        r"^(\s+[^\s#:]+:\s*)"                                # 1: "  name: "
        r"(rtsp://(?:[^/@\s]*@)?(?:" + hosts + r")"
        + re.escape(f":{RTSP_PORT}") + r"/"
        r"([^/\s]+)_live)\s*$"                               # 2: url, 3: device_id
    )


def ensure_go2rtc_config() -> None:
    """Create go2rtc.yaml if it is missing so go2rtc has something to read."""
    try:
        if not GO2RTC_CONFIG.exists():
            GO2RTC_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            GO2RTC_CONFIG.write_text(GO2RTC_DEFAULT_CONFIG)
            print(f"Created {GO2RTC_CONFIG}")
    except Exception as e:
        print(f"Could not create {GO2RTC_CONFIG}: {e}")


def go2rtc_streams() -> dict[str, str]:
    """stream name → device_id, parsed from go2rtc.yaml."""
    found: dict[str, str] = {}
    try:
        cfg = yaml.safe_load(GO2RTC_CONFIG.read_text()) or {}
        for name, url in (cfg.get("streams") or {}).items():
            if isinstance(url, str):
                m = re.search(r"/([^/]+)_live", url)
                if m:
                    found[name] = m.group(1)
    except Exception:
        pass
    return found


def _stream_slug(name: str, device_id: str, taken: set[str]) -> str:
    """A go2rtc stream name derived from a friendly name.

    Only ASCII letters, digits and underscores survive, so 'Vordertür' becomes
    'vordertur'. The friendly name itself is kept separately in settings, which
    is what the dashboard displays.
    """
    ascii_name = (unicodedata.normalize("NFKD", name)
                  .encode("ascii", "ignore").decode())
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")
    if not slug:
        slug = f"camera_{device_id[-6:]}"
    base, suffix = slug, 2
    while slug in taken:
        slug = f"{base}_{suffix}"
        suffix += 1
    taken.add(slug)
    return slug


def _go2rtc_delete_stream(name: str) -> bool:
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.delete(f"{GO2RTC_URL}/api/streams", params={"src": name})
            return resp.status_code < 300
    except Exception as e:
        print(f"go2rtc API unreachable while removing '{name}': {e}")
    return False


def _go2rtc_put_stream(name: str, src: str) -> bool:
    """Register or update a stream in the running go2rtc via its REST API.

    Avoids a container restart, which would drop every active viewer.
    """
    try:
        with httpx.Client(timeout=5) as client:
            for method in ("PUT", "POST"):
                resp = client.request(
                    method, f"{GO2RTC_URL}/api/streams",
                    params={"name": name, "src": src},
                )
                if resp.status_code < 300:
                    return True
    except Exception as e:
        print(f"go2rtc API unreachable for stream '{name}': {e}")
    return False


def sync_go2rtc_credentials() -> None:
    """Rewrite stream URLs in go2rtc.yaml that are out of date.

    ring-mqtt only writes its livestream credentials once it has connected;
    older configs contain ${RTSP_USER}/${RTSP_PASS} placeholders that go2rtc no
    longer receives; and an entry may name the wrong host if it was written by a
    backend running outside Docker. All three are repaired here.
    """
    if not GO2RTC_CONFIG.exists():
        return
    try:
        lines = GO2RTC_CONFIG.read_text().splitlines(keepends=True)
        changed: dict[str, str] = {}
        pattern = _stream_line_pattern()
        for i, line in enumerate(lines):
            m = pattern.match(line.rstrip("\n"))
            if not m:
                continue
            prefix, current, device_id = m.groups()
            wanted = rtsp_url(device_id, GO2RTC_RTSP_HOST)
            if current != wanted:
                lines[i] = f"{prefix}{wanted}\n"
                changed[prefix.strip().rstrip(":")] = wanted
        if not changed:
            return
        GO2RTC_CONFIG.write_text("".join(lines))
        print(f"Updated RTSP credentials for {len(changed)} stream(s)")
        for name, url in changed.items():
            _go2rtc_put_stream(name, url)
    except Exception as e:
        print(f"Credential sync error: {e}")

def apply_camera_selection(selections: list) -> dict:
    """Write the user's camera choices to go2rtc.yaml and the running go2rtc.

    Only entries for the given devices are touched — comments and hand-written
    streams pointing at other hardware are preserved.
    """
    ensure_go2rtc_config()
    settings = load_settings()
    names: dict[str, str] = dict(settings.get("camera_names") or {})
    disabled: set[str] = set(settings.get("disabled_cameras") or [])

    lines = GO2RTC_CONFIG.read_text().splitlines(keepends=True)
    pattern = _stream_line_pattern()
    existing: dict[str, int] = {}
    for i, line in enumerate(lines):
        m = pattern.match(line.rstrip("\n"))
        if m:
            existing[m.group(3)] = i

    chosen_ids = {s.device_id for s in selections}
    taken = {n for n, d in go2rtc_streams().items() if d not in chosen_ids}

    drop: set[int] = set()
    appended: list[str] = []
    registered: list[tuple[str, str]] = []
    removed: list[str] = []

    for sel in selections:
        index = existing.get(sel.device_id)

        if not sel.enabled:
            disabled.add(sel.device_id)
            names.pop(sel.device_id, None)
            if index is not None:
                drop.add(index)
                match = pattern.match(lines[index].rstrip("\n"))
                if match:
                    removed.append(match.group(1).strip().rstrip(":"))
            continue

        disabled.discard(sel.device_id)
        friendly = sel.name.strip() or f"Camera {sel.device_id[-6:].upper()}"
        names[sel.device_id] = friendly

        slug = _stream_slug(friendly, sel.device_id, taken)
        src = rtsp_url(sel.device_id, GO2RTC_RTSP_HOST)
        entry = f"  {slug}: {src}\n"
        registered.append((slug, src))

        if index is not None:
            previous = pattern.match(lines[index].rstrip("\n"))
            if previous:
                old_name = previous.group(1).strip().rstrip(":")
                if old_name != slug:
                    removed.append(old_name)
            lines[index] = entry
        else:
            appended.append(entry)

    # Rebuild in one pass so removals cannot shift the indices of replacements.
    out = [line for i, line in enumerate(lines) if i not in drop]
    if appended:
        anchor = next((i for i, l in enumerate(out) if l.strip() == "streams:"), None)
        if anchor is None:
            out.append("streams:\n")
            anchor = len(out) - 1
        out[anchor + 1:anchor + 1] = appended

    GO2RTC_CONFIG.write_text("".join(out))

    settings["camera_names"] = names
    settings["disabled_cameras"] = sorted(disabled)
    save_settings(settings)

    _discovered_devices.update(s.device_id for s in selections if s.enabled)
    for name in removed:
        _go2rtc_delete_stream(name)
    for slug, src in registered:
        _go2rtc_put_stream(slug, src)

    return {"enabled": len(registered), "disabled": len(disabled)}

# ── Auto-discovery ────────────────────────────────────────────────────────────

_discovered_devices: set[str] = set()
_discovery_lock = threading.Lock()


def _check_auto_discovery(device_id: str) -> None:
    """Add a stream entry for device_id to go2rtc.yaml if it has none yet."""
    if device_id in _discovered_devices:
        return
    # A camera the user switched off must not reappear on the next MQTT message.
    if device_id in set(load_settings().get("disabled_cameras") or []):
        return

    with _discovery_lock:
        if device_id in _discovered_devices:
            return

        ensure_go2rtc_config()
        try:
            content = GO2RTC_CONFIG.read_text()

            # Already configured?
            if device_id in content:
                _discovered_devices.add(device_id)
                return

            # Build a safe stream name from last 6 chars of device_id
            stream_name = f"camera_{device_id[-6:]}"
            src = rtsp_url(device_id, GO2RTC_RTSP_HOST)

            # Insert after the 'streams:' key
            lines = content.splitlines(keepends=True)
            idx = next((i for i, l in enumerate(lines) if l.strip() == "streams:"), None)
            if idx is None:
                return
            lines.insert(idx + 1, f"  {stream_name}: {src}\n")
            GO2RTC_CONFIG.write_text("".join(lines))
            _discovered_devices.add(device_id)
            print(f"Auto-discovered device {device_id} → stream '{stream_name}'")

            # Register live so the new camera is streamable immediately. Only
            # fall back to a restart (which interrupts active viewers) if the
            # API call fails.
            if not _go2rtc_put_stream(stream_name, src):
                threading.Thread(target=restart_go2rtc, daemon=True).start()

        except Exception as e:
            print(f"Auto-discovery error for {device_id}: {e}")

# ── MQTT ──────────────────────────────────────────────────────────────────────

def setup_mqtt() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(client, userdata, flags, reason_code, properties):
        global _mqtt_connected
        _mqtt_connected = True
        print(f"MQTT connected (rc={reason_code})")
        client.subscribe("ring/#")

    def on_disconnect(client, userdata, flags, reason_code, properties):
        global _mqtt_connected
        _mqtt_connected = False

    def on_message(client, userdata, msg):
        global _loop
        topic  = msg.topic
        parts  = topic.split("/")

        # ── Snapshot: binary JPEG (do NOT decode to string) ───────────────────
        # ring/<loc>/camera/<device_id>/snapshot/image
        if (len(parts) == 6 and parts[2] == "camera"
                and parts[4] == "snapshot" and parts[5] == "image"):
            device_id = parts[3]
            snapshots[device_id] = msg.payload
            return

        # ── Text-based topics ─────────────────────────────────────────────────
        try:
            payload = msg.payload.decode("utf-8", errors="replace")

            # motion/attributes: {"personDetected": true/false, ...}
            # ring/<loc>/camera/<device_id>/motion/attributes
            if (len(parts) == 6 and parts[2] == "camera"
                    and parts[4] == "motion" and parts[5] == "attributes"):
                try:
                    motion_attrs[parts[3]] = json.loads(payload)
                except Exception:
                    pass
                return

            # motion / ding events  (ring/<loc>/camera/<id>/motion|ding/state ON)
            if (len(parts) == 6 and parts[2] == "camera"
                    and parts[5] == "state" and payload == "ON"):
                kind = parts[4]
                if kind in ("motion", "ding"):
                    device_id = parts[3]
                    person = (
                        motion_attrs.get(device_id, {}).get("personDetected", False)
                        if kind == "motion" else False
                    )
                    event: dict = {
                        "id":             str(uuid.uuid4()),
                        "device_id":      device_id,
                        "location_id":    parts[1],
                        "kind":           kind,
                        "timestamp":      datetime.now(timezone.utc).isoformat(),
                        "person_detected": person,
                    }
                    events.insert(0, event)
                    if len(events) > 100:
                        events.pop()
                    schedule(broadcast({"type": "event", "data": event}))
                    schedule(send_notification(event))

                    # Auto-discover new cameras
                    _check_auto_discovery(device_id)

            # info/state: battery, WiFi, firmware
            # ring/<loc>/<camera|chime>/<device_id>/info/state
            if (len(parts) == 6 and parts[4] == "info" and parts[5] == "state"):
                device_type = parts[2]
                device_id   = parts[3]
                location_id = parts[1]

                # Cameras publish info/state on every ring-mqtt startup — use it
                # for auto-discovery so cameras appear without waiting for a motion event.
                if device_type == "camera":
                    _check_auto_discovery(device_id)

                try:
                    data = json.loads(payload)
                    state = device_states.setdefault(device_id, {
                        "id": device_id, "type": device_type, "location_id": location_id,
                    })
                    state.update({
                        "battery_level": data.get("batteryLevel"),
                        "firmware":      data.get("firmwareStatus"),
                        "last_update":   data.get("lastUpdate"),
                        "wifi_network":  data.get("wirelessNetwork"),
                        "wifi_signal":   data.get("wirelessSignal"),
                    })
                    schedule(broadcast({"type": "device_state",
                                        "device_id": device_id, "data": state}))

                    # Low battery alert
                    battery = data.get("batteryLevel")
                    if battery is not None:
                        cfg = load_settings()
                        threshold = cfg.get("low_battery_threshold", 20)
                        if cfg.get("notify_on_low_battery", True) and battery <= threshold:
                            if device_id not in _low_battery_notified:
                                _low_battery_notified.add(device_id)
                                schedule(send_device_alert(
                                    "Low Battery",
                                    f"Battery at {battery}% on {device_id}",
                                ))
                        elif battery > threshold:
                            _low_battery_notified.discard(device_id)
                except Exception:
                    pass

            # availability: connection lost/restored
            # ring/<loc>/<camera|chime>/<device_id>/status  — five segments, and
            # the segment is "status". ring-mqtt builds it as
            # `${deviceTopic}/status` (devices/base-ring-device.js); matching
            # "availability" over six segments never fired at all.
            if (len(parts) == 5 and parts[4] == "status"):
                device_id   = parts[3]
                status      = payload.strip().lower()
                prev        = _device_availability.get(device_id)
                _device_availability[device_id] = status
                if status == "offline" and prev != "offline":
                    cfg = load_settings()
                    if cfg.get("notify_on_connection_lost", True):
                        schedule(send_device_alert(
                            "Device Offline",
                            f"Connection lost to device {device_id}",
                        ))

            # Auto-discover cameras from info topics too
            if (len(parts) == 6 and parts[4] == "info" and parts[2] == "camera"):
                _check_auto_discovery(parts[3])

        except Exception as e:
            print(f"MQTT message error: {e}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"MQTT connect failed: {e}")
    return client

# ── Auth middleware ───────────────────────────────────────────────────────────

_UNPROTECTED_PATHS = {"/api/app/status", "/api/app/login", "/api/status",
                      "/api/setup/state"}
_PROTECTED_PREFIXES = ("/api/", "/ws/", "/stream/", "/recordings/")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = load_settings()
        if not settings.get("app_password_hash"):
            return await call_next(request)

        path = request.url.path
        if path in _UNPROTECTED_PATHS:
            return await call_next(request)

        token = request.cookies.get("ring_session", "")
        if token and token in app_sessions:
            return await call_next(request)

        # Block protected API / streaming paths
        if any(path.startswith(p) for p in _PROTECTED_PREFIXES):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        # Static files pass through (React app renders the login screen)
        return await call_next(request)

# ── App lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    _loop = asyncio.get_event_loop()
    ensure_go2rtc_config()
    sync_go2rtc_credentials()
    adopt_existing_install()
    app.state.mqtt = setup_mqtt()
    yield
    app.state.mqtt.loop_stop()


app = FastAPI(lifespan=lifespan)
app.add_middleware(AuthMiddleware)

# ── Pydantic models ───────────────────────────────────────────────────────────

class RingLoginRequest(BaseModel):
    email: str
    password: str

class RingVerifyRequest(BaseModel):
    session_id: str
    code: str

class SettingsRequest(BaseModel):
    ha_url: str = ""
    ha_token: str | None = None
    record_motion: bool = True
    record_ding: bool = True
    record_duration: int = 60
    retention_days: int = 30
    notify_url: str = ""
    notify_on_motion: bool = True
    notify_on_ding: bool = True
    notify_on_low_battery: bool = True
    low_battery_threshold: int = 20
    notify_on_connection_lost: bool = True

class TestNotificationRequest(BaseModel):
    notify_url: str = ""

class CameraSelection(BaseModel):
    device_id: str
    name: str = ""
    enabled: bool = True

class CameraSelectionRequest(BaseModel):
    cameras: list[CameraSelection]

class AppLoginRequest(BaseModel):
    password: str

class SetPasswordRequest(BaseModel):
    password: str

# ── App authentication ────────────────────────────────────────────────────────

@app.get("/api/app/status")
async def app_auth_status(request: Request):
    settings = load_settings()
    has_password = bool(settings.get("app_password_hash"))
    if not has_password:
        return {"auth_required": False, "authenticated": True}
    token = request.cookies.get("ring_session", "")
    return {
        "auth_required": True,
        "authenticated": bool(token and token in app_sessions),
    }


@app.post("/api/app/login")
async def app_login(req: AppLoginRequest, response: Response):
    settings = load_settings()
    password_hash = settings.get("app_password_hash", "")
    if not password_hash:
        return {"success": True}
    if not bcrypt.checkpw(req.password.encode(), password_hash.encode()):
        raise HTTPException(401, "Wrong password")
    token = secrets.token_urlsafe(32)
    app_sessions.add(token)
    response.set_cookie(
        "ring_session", token,
        httponly=True, samesite="lax",
        max_age=86400 * 30,  # 30 days
    )
    return {"success": True}


@app.post("/api/app/logout")
async def app_logout(request: Request, response: Response):
    token = request.cookies.get("ring_session", "")
    app_sessions.discard(token)
    response.delete_cookie("ring_session")
    return {"success": True}


@app.post("/api/app/set-password")
async def set_password(req: SetPasswordRequest):
    settings = load_settings()
    if req.password:
        hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
        settings["app_password_hash"] = hashed
    else:
        settings["app_password_hash"] = ""
    save_settings(settings)
    return {"success": True}

# ── Status ────────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    cfg = load_settings()
    return {
        "ring_configured": ring_token_present(),
        "ha_configured": bool(cfg.get("ha_url") and cfg.get("ha_token")),
    }

# ── Guided setup ──────────────────────────────────────────────────────────────

def _tcp_open(host: str, port: str | int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout):
            return True
    except Exception:
        return False


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".ring-off-write-test"
        probe.write_text("")
        probe.unlink()
        return True
    except Exception:
        return False


def setup_is_complete() -> bool:
    return bool(load_settings().get("setup_complete"))


def adopt_existing_install() -> None:
    """Mark setup done for deployments that were configured before the wizard.

    Without this, upgrading users would be sent back through onboarding for an
    install that already works. It runs only when the flag has never been
    written: once the user has finished or explicitly restarted setup, that
    choice is theirs, and re-adopting here would undo "Run setup again" on the
    next restart.
    """
    stored = json.loads(SETTINGS_FILE.read_text()) if SETTINGS_FILE.exists() else {}
    if "setup_complete" in stored:
        return
    if ring_token_present():
        settings = load_settings()
        settings["setup_complete"] = True
        save_settings(settings)
        print("Existing Ring configuration detected — skipping guided setup")


@app.get("/api/setup/state")
async def setup_state():
    cameras = [d for d in device_states.values() if d.get("type") == "camera"]
    return {
        "complete":           setup_is_complete(),
        "ring_authenticated": ring_token_present(),
        "app_password_set":   bool(load_settings().get("app_password_hash")),
        "cameras_found":      len(cameras),
    }


@app.get("/api/setup/preflight")
async def setup_preflight():
    """Health of everything onboarding depends on, with a fix for each failure."""
    checks: list[dict] = []

    def add(key: str, label: str, ok: bool, hint: str, required: bool = True) -> None:
        checks.append({"key": key, "label": label, "ok": ok,
                       "required": required, "hint": None if ok else hint})

    mqtt_ok = _mqtt_connected or await asyncio.to_thread(_tcp_open, MQTT_HOST, MQTT_PORT)
    add("mqtt", "MQTT broker", mqtt_ok,
        f"No broker at {MQTT_HOST}:{MQTT_PORT}. Run `docker compose ps mosquitto` "
        f"— without it no events or devices arrive.")

    add("ring_mqtt", "ring-mqtt bridge",
        await asyncio.to_thread(_tcp_open, RTSP_HOST, RTSP_PORT),
        "ring-mqtt is not answering. It shuts down on startup when "
        "data/ring-mqtt/config.json is missing — check `docker compose logs ring-mqtt`.")

    go2rtc_ok = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            go2rtc_ok = (await client.get(f"{GO2RTC_URL}/api/streams")).status_code < 400
    except Exception:
        pass
    add("go2rtc", "go2rtc streaming", go2rtc_ok,
        f"No response from {GO2RTC_URL}. Everything else works; live video will not.",
        required=False)

    add("config", "Camera config writable", _writable(GO2RTC_CONFIG.parent),
        f"Cannot write to {GO2RTC_CONFIG.parent}. Cameras cannot be added automatically.")

    add("videos", "Recordings folder writable", _writable(VIDEO_PATH),
        f"Cannot write to {VIDEO_PATH}. Event clips cannot be saved.", required=False)

    return {
        "ok": all(c["ok"] for c in checks if c["required"]),
        "checks": checks,
    }


def camera_config_list() -> list[dict]:
    """Every known camera with its name and on/off state.

    device_states only holds what MQTT has published since this process started,
    and ring-mqtt re-announces on its own schedule. Cameras already configured,
    named or disabled are merged in, so a restart never makes a working install
    look empty.
    """
    settings = load_settings()
    names = settings.get("camera_names") or {}
    disabled = set(settings.get("disabled_cameras") or [])

    chime_ids = {d for d, s in device_states.items() if s.get("type") == "chime"}
    camera_ids = ({d for d, s in device_states.items() if s.get("type") == "camera"}
                  | set(go2rtc_streams().values())
                  | set(names) | disabled) - chime_ids

    return [
        {
            "device_id":     device_id,
            "name":          names.get(device_id) or f"Camera {device_id[-6:].upper()}",
            "enabled":       device_id not in disabled,
            "battery_level": device_states.get(device_id, {}).get("battery_level"),
            "wifi_signal":   device_states.get(device_id, {}).get("wifi_signal"),
            "has_snapshot":  device_id in snapshots,
        }
        for device_id in sorted(camera_ids)
    ]


@app.get("/api/cameras/config")
async def get_camera_config():
    """Camera names and toggles, for the wizard and the settings sheet alike."""
    return camera_config_list()


@app.post("/api/cameras/config")
async def save_camera_config(req: CameraSelectionRequest):
    return apply_camera_selection(req.cameras)


@app.get("/api/setup/discovered")
async def setup_discovered():
    """Devices seen on MQTT so far, for live progress during onboarding."""
    chime_ids = {d for d, s in device_states.items() if s.get("type") == "chime"}
    cameras = camera_config_list()
    chimes = [
        {
            "device_id":     device_id,
            "name":          f"Chime {device_id[-4:].upper()}",
            "enabled":       True,
            "battery_level": device_states[device_id].get("battery_level"),
            "wifi_signal":   device_states[device_id].get("wifi_signal"),
            "has_snapshot":  False,
        }
        for device_id in sorted(chime_ids)
    ]
    return {
        "ring_authenticated": ring_token_present(),
        "mqtt_connected":     _mqtt_connected,
        "cameras":            cameras,
        "chimes":             chimes,
    }


@app.post("/api/setup/test-notification")
async def setup_test_notification(req: TestNotificationRequest):
    """Prove the notification URL works before relying on it for a real event."""
    url = (req.notify_url or load_settings().get("notify_url", "")).strip()
    if not url:
        raise HTTPException(400, "Enter a notification URL first")
    ok, detail = await post_notification(
        url, "Ring Off", "Test notification — alerts are working.")
    return {"ok": ok, "detail": detail}


@app.post("/api/setup/complete")
async def setup_finish():
    settings = load_settings()
    settings["setup_complete"] = True
    save_settings(settings)
    return {"success": True}


@app.post("/api/setup/reset")
async def setup_reset():
    """Re-run the wizard from the settings sheet."""
    settings = load_settings()
    settings["setup_complete"] = False
    save_settings(settings)
    return {"success": True}

# ── Ring auth ─────────────────────────────────────────────────────────────────

@app.post("/api/auth/ring")
async def ring_login(req: RingLoginRequest):
    auth = Auth(USER_AGENT, None, lambda t: None)
    try:
        await auth.async_fetch_token(req.email, req.password)
        save_ring_token(auth._token["refresh_token"])
        await auth.async_close()
        restart_ring_mqtt()
        return {"success": True}
    except Requires2FAError:
        sid = str(uuid.uuid4())
        pending_auth[sid] = {"auth": auth, "email": req.email, "password": req.password}
        return {"needs_2fa": True, "session_id": sid}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/auth/ring/verify")
async def ring_verify(req: RingVerifyRequest):
    session = pending_auth.get(req.session_id)
    if not session:
        raise HTTPException(400, "Invalid or expired session — please log in again")
    auth: Auth = session["auth"]
    try:
        await auth.async_fetch_token(session["email"], session["password"], req.code)
        save_ring_token(auth._token["refresh_token"])
        await auth.async_close()
        pending_auth.pop(req.session_id, None)
        restart_ring_mqtt()
        return {"success": True}
    except Exception as e:
        # The session is deliberately kept: a mistyped code, or a failure while
        # saving the token, should not force the user back through email and
        # password. Abandoned sessions are cleaned up by their TTL.
        raise HTTPException(400, str(e))

# ── Cameras ───────────────────────────────────────────────────────────────────

@app.get("/api/cameras")
async def get_cameras():
    # go2rtc uses lazy RTSP connections: producers is only populated while a stream
    # is actively being viewed. Parse go2rtc.yaml directly so device_id is always
    # available regardless of whether anyone is currently streaming.
    sync_go2rtc_credentials()
    yaml_device_ids = go2rtc_streams()
    friendly_names = load_settings().get("camera_names") or {}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{GO2RTC_URL}/api/streams")
            streams = resp.json()
            cameras = []
            for name, info in streams.items():
                device_id = yaml_device_ids.get(name)
                if not device_id and isinstance(info, dict):
                    for p in info.get("producers", []):
                        m = re.search(r"/([^/]+)_live", p.get("url", ""))
                        if m:
                            device_id = m.group(1)
                            break
                cameras.append({
                    "id": name,
                    "name": (friendly_names.get(device_id) if device_id else None)
                            or name.replace("_", " ").title(),
                    "stream": name,
                    "device_id": device_id,
                    "has_snapshot": device_id in snapshots if device_id else False,
                })
            return cameras
    except Exception:
        return []

# ── Snapshot ──────────────────────────────────────────────────────────────────

@app.get("/api/snapshot/{device_id}")
async def get_snapshot(device_id: str):
    data = snapshots.get(device_id)
    if not data:
        raise HTTPException(404, "No snapshot available")
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "no-cache"})

# ── Events / devices ──────────────────────────────────────────────────────────

@app.get("/api/events")
async def get_events():
    return events


@app.get("/api/devices")
async def get_devices():
    return device_states

# ── Settings / HA ─────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    s = load_settings()
    return {
        "ha_url":           s.get("ha_url", ""),
        "ha_token_set":     bool(s.get("ha_token")),
        "record_motion":    s.get("record_motion", True),
        "record_ding":      s.get("record_ding", True),
        "record_duration":  s.get("record_duration", 60),
        "retention_days":   s.get("retention_days", 30),
        "notify_url":                s.get("notify_url", ""),
        "notify_on_motion":          s.get("notify_on_motion", True),
        "notify_on_ding":            s.get("notify_on_ding", True),
        "notify_on_low_battery":     s.get("notify_on_low_battery", True),
        "low_battery_threshold":     s.get("low_battery_threshold", 20),
        "notify_on_connection_lost": s.get("notify_on_connection_lost", True),
        "app_password_set": bool(s.get("app_password_hash")),
    }


@app.post("/api/settings")
async def save_settings_route(req: SettingsRequest):
    current = load_settings()
    updated = {
        **current,
        "ha_url":           req.ha_url,
        "ha_token":         req.ha_token if req.ha_token else current.get("ha_token", ""),
        "record_motion":    req.record_motion,
        "record_ding":      req.record_ding,
        "record_duration":  max(10, min(300, req.record_duration)),
        "retention_days":   max(0, req.retention_days),
        "notify_url":                req.notify_url,
        "notify_on_motion":          req.notify_on_motion,
        "notify_on_ding":            req.notify_on_ding,
        "notify_on_low_battery":     req.notify_on_low_battery,
        "low_battery_threshold":     max(1, min(100, req.low_battery_threshold)),
        "notify_on_connection_lost": req.notify_on_connection_lost,
    }
    save_settings(updated)
    return {"success": True}


@app.get("/api/ha/entities")
async def get_ha_entities():
    settings = load_settings()
    if not settings.get("ha_url") or not settings.get("ha_token"):
        raise HTTPException(400, "Home Assistant not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings['ha_url'].rstrip('/')}/api/states",
                headers={"Authorization": f"Bearer {settings['ha_token']}"},
            )
            if resp.status_code != 200:
                raise HTTPException(resp.status_code, "HA API error")
            all_states = resp.json()
            ring_entities = [
                e for e in all_states
                if "ring" in e["entity_id"].lower()
                or "doorbell" in e["entity_id"].lower()
                or "haustür" in e["attributes"].get("friendly_name", "").lower()
            ]
            return ring_entities
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Could not reach Home Assistant: {e}")

# ── Recordings browser ────────────────────────────────────────────────────────

@app.get("/api/recordings")
async def get_recordings():
    if not VIDEO_PATH.exists():
        return []
    clips = []
    for device_dir in sorted(VIDEO_PATH.iterdir()):
        if not device_dir.is_dir():
            continue
        for clip in sorted(device_dir.glob("*.mp4"), reverse=True):
            stat = clip.stat()
            clips.append({
                "device_id": device_dir.name,
                "filename":  clip.name,
                "path":      f"{device_dir.name}/{clip.name}",
                "size":      stat.st_size,
                "created":   datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "kind":      "ding" if "_ding" in clip.stem else "motion",
            })
    return clips


@app.get("/recordings/files/{device_id}/{filename}")
async def serve_recording(device_id: str, filename: str, request: Request):
    if ".." in device_id or ".." in filename or "/" in device_id or "/" in filename:
        raise HTTPException(400, "Invalid path")
    clip_path = VIDEO_PATH / device_id / filename
    if not clip_path.exists() or clip_path.suffix != ".mp4":
        raise HTTPException(404, "Clip not found")

    file_size = clip_path.stat().st_size
    range_header = request.headers.get("range")

    def make_iter(start: int = 0, end: int | None = None):
        chunk_size = 65536
        with open(clip_path, "rb") as f:
            f.seek(start)
            remaining = (end - start + 1) if end is not None else None
            while True:
                to_read = min(chunk_size, remaining) if remaining is not None else chunk_size
                chunk = f.read(to_read)
                if not chunk:
                    break
                yield chunk
                if remaining is not None:
                    remaining -= len(chunk)
                    if remaining <= 0:
                        break

    if range_header:
        # Support Range requests for video scrubbing
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            end = min(end, file_size - 1)
            return StreamingResponse(
                make_iter(start, end),
                status_code=206,
                media_type="video/mp4",
                headers={
                    "Content-Range":  f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(end - start + 1),
                    "Accept-Ranges":  "bytes",
                },
            )

    return StreamingResponse(
        make_iter(),
        media_type="video/mp4",
        headers={
            "Content-Length":      str(file_size),
            "Accept-Ranges":       "bytes",
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@app.delete("/api/recordings/{device_id}/{filename}")
async def delete_recording(device_id: str, filename: str):
    if ".." in device_id or ".." in filename or "/" in device_id or "/" in filename:
        raise HTTPException(400, "Invalid path")
    clip_path = VIDEO_PATH / device_id / filename
    if not clip_path.exists():
        raise HTTPException(404, "Clip not found")
    clip_path.unlink()
    return {"success": True}

# ── MJPEG streaming via ffmpeg ────────────────────────────────────────────────

async def _get_device_id(stream_name: str) -> str | None:
    # go2rtc.yaml first: producers is empty unless the stream is already being
    # viewed, which is exactly when the MJPEG fallback is needed.
    device_id = go2rtc_streams().get(stream_name)
    if device_id:
        return device_id
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{GO2RTC_URL}/api/streams")
            streams = resp.json()
            for p in streams.get(stream_name, {}).get("producers", []):
                m = re.search(r"/([^/]+)_live", p.get("url", ""))
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


@app.get("/stream/{stream_name}")
async def stream_mjpeg(stream_name: str):
    device_id = await _get_device_id(stream_name)
    if not device_id:
        raise HTTPException(404, f"No RTSP source found for stream '{stream_name}'")

    src = rtsp_url(device_id)

    async def generate():
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-timeout", "30000000",
            "-i", src,
            "-an",
            "-f", "mpjpeg",
            "-q:v", "5",
            "-r", "15",
            "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                proc.kill()
            except Exception:
                pass
            await proc.wait()

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=ffmpeg",
    )

# ── go2rtc HTTP proxy ─────────────────────────────────────────────────────────

@app.api_route("/proxy/go2rtc/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy_go2rtc(request: Request, path: str):
    url = f"{GO2RTC_URL}/{path}"
    params = dict(request.query_params)
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                params=params,
                headers=forward_headers,
                content=await request.body(),
            )
        skip = {"transfer-encoding", "connection", "keep-alive"}
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in skip}
        return Response(content=resp.content, status_code=resp.status_code, headers=headers)
    except Exception as e:
        raise HTTPException(502, f"go2rtc unreachable: {e}")

# ── go2rtc WebSocket proxy (WebRTC video streams) ─────────────────────────────

@app.websocket("/ws/video")
async def video_proxy(websocket: WebSocket, src: str):
    await websocket.accept()
    upstream_url = f"{GO2RTC_WS}/api/ws?src={src}"
    try:
        async with ws_lib.connect(upstream_url) as upstream:
            async def to_upstream():
                # go2rtc's signaling is JSON *text* frames. iter_bytes() raises
                # on a text message, and the resulting silent failure meant the
                # browser's WebRTC offer never reached go2rtc — the stream just
                # stayed black. Forward whatever frame type actually arrives.
                try:
                    while True:
                        message = await websocket.receive()
                        if message["type"] == "websocket.disconnect":
                            break
                        if message.get("text") is not None:
                            await upstream.send(message["text"])
                        elif message.get("bytes") is not None:
                            await upstream.send(message["bytes"])
                except (WebSocketDisconnect, Exception):
                    pass

            async def to_client():
                try:
                    async for message in upstream:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except Exception:
                    pass

            await asyncio.gather(to_upstream(), to_client())
    except Exception as e:
        print(f"Video proxy error ({src}): {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

# ── Events WebSocket ──────────────────────────────────────────────────────────

@app.websocket("/ws/events")
async def events_ws(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    await websocket.send_json({"type": "history", "data": events})
    await websocket.send_json({"type": "device_states", "data": device_states})
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        ws_clients.discard(websocket)

# ── Static files ──────────────────────────────────────────────────────────────

# Built by the Docker image at /app/static. Absent when running the backend
# directly for development, where vite serves the frontend on :5173 and proxies
# the API here — mounting unconditionally would crash startup.
STATIC_DIR = Path(os.getenv("STATIC_DIR", "static"))
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    print(f"No static directory at '{STATIC_DIR}' — serving API only")
