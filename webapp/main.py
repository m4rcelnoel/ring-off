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
import json
import os
import re
import secrets
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
RTSP_USER         = os.getenv("RTSP_USER",              "ringuser")
RTSP_PASS         = os.getenv("RTSP_PASS",              "ringpass")
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


def save_ring_token(refresh_token: str) -> None:
    cfg = load_ring_config()
    cfg["ring_token"] = refresh_token
    RING_MQTT_CONFIG.write_text(json.dumps(cfg, indent=2))


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

# ── WebSocket broadcast ───────────────────────────────────────────────────────

async def broadcast(message: dict) -> None:
    dead: set[WebSocket] = set()
    for ws in ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    ws_clients -= dead

# ── Push notifications ────────────────────────────────────────────────────────

async def send_notification(event: dict) -> None:
    """Send push notification for motion/ding events via ntfy.sh / Gotify / Pushover."""
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

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            # ntfy.sh: POST with Title header and plain-text body
            # Gotify: POST /message?token=TOKEN with JSON
            # Detect Gotify by /message path; otherwise use ntfy format
            if "/message" in notify_url:
                await client.post(notify_url, json={"title": title, "message": body, "priority": 5})
            else:
                await client.post(
                    notify_url,
                    headers={"Title": title},
                    content=body.encode(),
                )
    except Exception as e:
        print(f"Notification error: {e}")

async def send_device_alert(title: str, body: str) -> None:
    """Send a push notification for device-health events (low battery, connection lost)."""
    settings = load_settings()
    notify_url = settings.get("notify_url", "").strip()
    if not notify_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            if "/message" in notify_url:
                await client.post(notify_url, json={"title": title, "message": body, "priority": 5})
            else:
                await client.post(notify_url, headers={"Title": title}, content=body.encode())
    except Exception as e:
        print(f"Device alert error: {e}")

# ── Auto-discovery ────────────────────────────────────────────────────────────

_discovered_devices: set[str] = set()
_discovery_lock = threading.Lock()


def _check_auto_discovery(device_id: str) -> None:
    """If device_id is not in go2rtc.yaml, append a new stream entry and restart go2rtc."""
    if not GO2RTC_CONFIG.exists():
        return
    if device_id in _discovered_devices:
        return

    with _discovery_lock:
        if device_id in _discovered_devices:
            return

        try:
            content = GO2RTC_CONFIG.read_text()

            # Already configured?
            if device_id in content:
                _discovered_devices.add(device_id)
                return

            # Build a safe stream name from last 6 chars of device_id
            stream_name = f"camera_{device_id[-6:]}"
            new_line = (
                f"  {stream_name}:"
                f" rtsp://${{RTSP_USER}}:${{RTSP_PASS}}@ring-mqtt:8554/{device_id}_live\n"
            )

            # Insert after the 'streams:' key
            lines = content.splitlines(keepends=True)
            idx = next((i for i, l in enumerate(lines) if l.strip() == "streams:"), None)
            if idx is None:
                return
            lines.insert(idx + 1, new_line)
            GO2RTC_CONFIG.write_text("".join(lines))
            _discovered_devices.add(device_id)
            print(f"Auto-discovered device {device_id} → stream '{stream_name}'")

            threading.Thread(target=restart_go2rtc, daemon=True).start()

        except Exception as e:
            print(f"Auto-discovery error for {device_id}: {e}")

# ── RTSP credentials helper ───────────────────────────────────────────────────

def _rtsp_credentials() -> tuple[str, str]:
    cfg = load_ring_config()
    user   = cfg.get("livestream_user") or RTSP_USER
    passwd = cfg.get("livestream_pass") or RTSP_PASS
    return user, passwd

# ── MQTT ──────────────────────────────────────────────────────────────────────

def setup_mqtt() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(client, userdata, flags, reason_code, properties):
        print(f"MQTT connected (rc={reason_code})")
        client.subscribe("ring/#")

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
                    if _loop:
                        asyncio.run_coroutine_threadsafe(
                            broadcast({"type": "event", "data": event}), _loop)
                        asyncio.run_coroutine_threadsafe(
                            send_notification(event), _loop)

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
                    if _loop:
                        asyncio.run_coroutine_threadsafe(
                            broadcast({"type": "device_state",
                                       "device_id": device_id, "data": state}), _loop)

                    # Low battery alert
                    battery = data.get("batteryLevel")
                    if battery is not None and _loop:
                        cfg = load_settings()
                        threshold = cfg.get("low_battery_threshold", 20)
                        if cfg.get("notify_on_low_battery", True) and battery <= threshold:
                            if device_id not in _low_battery_notified:
                                _low_battery_notified.add(device_id)
                                asyncio.run_coroutine_threadsafe(
                                    send_device_alert(
                                        "Low Battery",
                                        f"Battery at {battery}% on {device_id}",
                                    ), _loop)
                        elif battery > threshold:
                            _low_battery_notified.discard(device_id)
                except Exception:
                    pass

            # availability: connection lost/restored
            # ring/<loc>/<camera|chime>/<device_id>/availability
            if (len(parts) == 6 and parts[4] == "availability"):
                device_id   = parts[3]
                status      = payload.strip().lower()
                prev        = _device_availability.get(device_id)
                _device_availability[device_id] = status
                if status == "offline" and prev != "offline" and _loop:
                    cfg = load_settings()
                    if cfg.get("notify_on_connection_lost", True):
                        asyncio.run_coroutine_threadsafe(
                            send_device_alert(
                                "Device Offline",
                                f"Connection lost to device {device_id}",
                            ), _loop)

            # Auto-discover cameras from info topics too
            if (len(parts) == 6 and parts[4] == "info" and parts[2] == "camera"):
                _check_auto_discovery(parts[3])

        except Exception as e:
            print(f"MQTT message error: {e}")

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"MQTT connect failed: {e}")
    return client

# ── Auth middleware ───────────────────────────────────────────────────────────

_UNPROTECTED_PATHS = {"/api/app/status", "/api/app/login", "/api/status"}
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
    ring_cfg = load_ring_config()
    return {
        "ring_configured": bool(ring_cfg.get("ring_token")),
        "ha_configured": bool(cfg.get("ha_url") and cfg.get("ha_token")),
    }

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
    session = pending_auth.pop(req.session_id, None)
    if not session:
        raise HTTPException(400, "Invalid or expired session — please log in again")
    auth: Auth = session["auth"]
    try:
        await auth.async_fetch_token(session["email"], session["password"], req.code)
        save_ring_token(auth._token["refresh_token"])
        await auth.async_close()
        restart_ring_mqtt()
        return {"success": True}
    except Exception as e:
        await auth.async_close()
        raise HTTPException(400, str(e))

# ── Cameras ───────────────────────────────────────────────────────────────────

@app.get("/api/cameras")
async def get_cameras():
    # go2rtc uses lazy RTSP connections: producers is only populated while a stream
    # is actively being viewed. Parse go2rtc.yaml directly so device_id is always
    # available regardless of whether anyone is currently streaming.
    yaml_device_ids: dict[str, str] = {}
    try:
        with open(GO2RTC_CONFIG) as f:
            cfg = yaml.safe_load(f)
        for stream_name, url in (cfg.get("streams") or {}).items():
            if isinstance(url, str):
                m = re.search(r"/([^/]+)_live", url)
                if m:
                    yaml_device_ids[stream_name] = m.group(1)
    except Exception:
        pass

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
                    "name": name.replace("_", " ").title(),
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

    user, passwd = _rtsp_credentials()
    rtsp_url = f"rtsp://{user}:{passwd}@{RTSP_HOST}:{RTSP_PORT}/{device_id}_live"

    async def generate():
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-timeout", "30000000",
            "-i", rtsp_url,
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
                try:
                    async for data in websocket.iter_bytes():
                        await upstream.send(data)
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

app.mount("/", StaticFiles(directory="static", html=True), name="static")
