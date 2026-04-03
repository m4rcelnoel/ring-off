# Ring Off

Self-hosted Ring doorbell management: live camera streams, motion & doorbell event recording, battery/WiFi monitoring — all without a Ring subscription.

> **No cloud. No subscription. Your data stays at home.**

![Ring Off Web Interface](image/webinterface.png)

---

## Tested Hardware

| Device | Status |
|---|---|
| Ring Video Doorbell 3 | ✅ Tested |

Other Ring cameras that work with [ring-mqtt](https://github.com/tsightler/ring-mqtt) should work too — battery cameras, wired doorbells, and indoor/outdoor cameras. If you've tested another model, feel free to open a PR.

---

## Features

- **WebRTC + MJPEG streams** — low-latency WebRTC via go2rtc's `video-rtc.js`, with MJPEG fallback
- **Snapshot previews** — camera cards show the latest JPEG thumbnail before you start a stream
- **Person detection** — motion events with an identified person get a distinct badge in the event feed
- **Motion & ding recording** — clips saved locally on every event, configurable per type and duration
- **Recordings browser** — browse, play, and delete clips directly from the sidebar
- **Clip retention policy** — auto-delete recordings older than a configurable number of days
- **Push notifications** — ntfy.sh and Gotify support; per-event-type toggles for motion, ding, low battery, and connection lost
- **Auto-discovery** — new cameras found in MQTT are automatically added to go2rtc (no manual config)
- **Password protection** — optional app-level login screen with bcrypt-hashed password
- **Real-time event feed** — motion and doorbell events pushed instantly via WebSocket
- **Device status** — battery level and WiFi signal for cameras; WiFi signal for chimes
- **Ring login in the UI** — OAuth2 with 2FA support, no manual config file editing
- **Home Assistant panel** — browse Ring-related HA entities directly from the dashboard
- **NAS-ready** — change one volume mount to store recordings on your NAS
- **Multi-arch Docker images** — runs on x86-64 and Raspberry Pi (arm64)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Your Network                           │
│                                                                 │
│   Browser                                                       │
│     │  HTTP / WebSocket                                         │
│     ▼                                                           │
│  ┌──────────────────────────────┐                               │
│  │   webapp  :8080              │  FastAPI backend              │
│  │   React frontend             │  + React UI (built-in)        │
│  └──────┬───────────────────────┘                               │
│         │                                                       │
│    ┌────┴──────────────────────────────────────┐                │
│    │                                           │                │
│    ▼  HTTP proxy / MJPEG stream                ▼  MQTT sub      │
│  ┌────────────────┐                   ┌─────────────────┐       │
│  │  go2rtc  :1984 │  RTSP relay       │  mosquitto:1883 │       │
│  └───────┬────────┘                   └────────┬────────┘       │
│          │  RTSP pull                          │  MQTT pub      │
│          ▼                                     ▼                │
│  ┌───────────────────────────────────────────────────────┐      │
│  │               ring-mqtt  :8554 (RTSP)                 │      │
│  │         Ring ↔ MQTT bridge + WebRTC → RTSP            │      │
│  └───────────────────────┬───────────────────────────────┘      │
│                          │  WebRTC / TLS                        │
│    ┌─────────────────┐   │                                      │
│    │  recorder       │   │                                      │
│    │  (ffmpeg clips) │   │                                      │
│    └────────┬────────┘   │                                      │
│             │ RTSP pull  │                                      │
│             └────────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                      Ring Cloud ☁️

Persistent data (./data/, gitignored)
  ├── ring-mqtt/    Ring OAuth token + RTSP credentials
  ├── webapp/       settings.json
  ├── videos/       recorded MP4 clips
  └── mosquitto/    MQTT message persistence
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Docker | 24+ |
| Docker Compose | v2 (plugin) |
| Ring account | any — subscription **not** required |

---

## Quick Start

**1. Clone the repository**

```bash
git clone https://github.com/m4rcelnoel/ring-off.git
cd ring-off
```

**2. Copy the config files**

```bash
cp .env.example .env
# You can leave it empty for now — credentials are filled in automatically after login

cp config/go2rtc.yaml.example config/go2rtc.yaml
# Edit this file to add your device IDs (or let auto-discovery handle it)
```

**3. Start the stack**

```bash
docker compose up -d
```

> **Optional services:** `go2rtc` (live streaming) and `recorder` (clip recording) are included by default. If you don't need one of them, comment out or remove its block in `docker-compose.yml`.

**4. Open the web UI and log in**

Navigate to **http://localhost:8080** and enter your Ring email and password.
If your account uses two-factor authentication, you will be prompted for the code.

After a successful login the refresh token is saved to `data/ring-mqtt/config.json`
and ring-mqtt is restarted automatically — no manual steps required.

---

## Stream Setup

Ring camera streams are served by **go2rtc**, which re-streams ring-mqtt's internal RTSP feeds.

> **Auto-discovery (recommended):** Ring Off automatically detects new cameras from MQTT and adds them to `config/go2rtc.yaml`. Just start the stack, log in, and wait a few seconds — cameras will appear without any manual config.

### Manual setup (optional)

If you prefer to name your cameras yourself, edit `config/go2rtc.yaml` (copy from `.example` first):

```bash
cp config/go2rtc.yaml.example config/go2rtc.yaml
```

#### Finding your device IDs

Start the stack, then watch MQTT topics for a few seconds:

```bash
docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v -W 10
```

Look for topics like:

```
ring/<location-id>/camera/<DEVICE_ID>/motion/state ON
```

Add each `<DEVICE_ID>` to `config/go2rtc.yaml`:

```yaml
streams:
  front_door: rtsp://${RTSP_USER}:${RTSP_PASS}@ring-mqtt:8554/DEVICE_ID_live
  back_door:  rtsp://${RTSP_USER}:${RTSP_PASS}@ring-mqtt:8554/DEVICE_ID_live
```

> **Privacy note:** `config/go2rtc.yaml` is gitignored because it contains your camera device IDs (hardware MAC addresses). Never commit it — use the `.example` file for version control.

Update `.env` with the credentials you use to log in to Ring:

```bash
RTSP_USER=your@email.com
RTSP_PASS=yourringpassword
```

Then restart:

```bash
docker compose restart go2rtc webapp
```

---

## Configuration

### Environment variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `RTSP_USER` | — | Ring account email (used for RTSP auth) |
| `RTSP_PASS` | — | Ring account password (used for RTSP auth) |

### Settings (web UI → Settings gear)

| Setting | Default | Description |
|---|---|---|
| Record on motion | ✅ | Save a clip when motion is detected |
| Record on ding | ✅ | Save a clip when the doorbell is pressed |
| Clip duration | 60 s | How long each clip is (10–300 s) |
| Clip retention | 30 days | Auto-delete recordings older than N days (0 = keep forever) |
| Notification URL | — | ntfy.sh topic URL or Gotify `/message?token=TOKEN` URL |
| Notify on motion | ✅ | Send push notification on motion events |
| Notify on ding | ✅ | Send push notification when doorbell rings |
| Notify on low battery | ✅ | Alert when a device battery drops below the threshold |
| Low battery threshold | 20% | Battery percentage that triggers the low battery alert |
| Notify on connection lost | ✅ | Alert when a device goes offline |
| App password | — | Protect the dashboard with a bcrypt password |

Settings are stored in `data/webapp/settings.json` and take effect immediately — no restart needed.

### Push Notifications

Paste a notification endpoint URL into Settings to receive alerts:

```
# ntfy.sh (free, no account needed for public topics)
https://ntfy.sh/your-secret-topic

# Gotify (self-hosted)
https://gotify.yourhost.com/message?token=YOUR_APP_TOKEN
```

### Service ports

| Service | Port | Purpose |
|---|---|---|
| webapp | **8080** | Web UI + API (expose this one) |
| go2rtc | 1984 | go2rtc web UI (optional, internal) |
| mosquitto | 1883 | MQTT broker (internal) |
| ring-mqtt | 8554 | RTSP streams (internal) |

---

## NAS Recording

To store recordings on a NAS, change the recorder volume in `docker-compose.yml`:

```yaml
recorder:
  volumes:
    - /mnt/nas/ring-videos:/videos   # ← your NAS mount point
```

Recordings are organised by device ID:

```
data/videos/
└── <device_id>/
    ├── 20260316_124334_motion.mp4
    └── 20260316_134512_ding.mp4
```

---

## Using an Existing MQTT Broker

If you already run a Mosquitto instance (e.g. as part of Home Assistant or another smart-home stack), you can point all services at it instead of starting the bundled one.

**1. Remove the `mosquitto` service from `docker-compose.yml`**

Delete or comment out the entire `mosquitto:` block and remove `mosquitto` from every `depends_on`.

**2. Update ring-mqtt's config to point at your broker**

ring-mqtt in Docker mode reads its MQTT connection from `data/ring-mqtt/config.json`, not from environment variables. Edit the file directly:

```json
{
  "mqtt_url": "mqtt://192.168.1.100:1883",
  "ring_token": "..."
}
```

For authenticated brokers:

```json
{
  "mqtt_url": "mqtt://myuser:mypassword@192.168.1.100:1883",
  "ring_token": "..."
}
```

For TLS (port 8883):

```json
{
  "mqtt_url": "mqtts://192.168.1.100:8883",
  "ring_token": "..."
}
```

**3. Update webapp and recorder environment variables**

```yaml
# docker-compose.yml

  webapp:
    environment:
      - MQTT_HOST=192.168.1.100
      - MQTT_PORT=1883

  recorder:
    environment:
      - MQTT_HOST=192.168.1.100
      - MQTT_PORT=1883
```

**4. Allow the `ring/#` topic on your broker**

ring-mqtt publishes and subscribes to the `ring/#` topic tree. Make sure your broker's ACL permits this for your user, or allows anonymous access from the Docker network.

Example ACL entry for Mosquitto:

```
user myuser
topic readwrite ring/#
```

**5. Restart**

```bash
docker compose up -d
```

---

## Home Assistant Integration

1. Open **Settings** in the web UI
2. Enter your HA URL (e.g. `http://homeassistant.local:8123`)
3. Create a Long-Lived Access Token in HA → Profile → Security
4. Paste the token and save

The **Home Assistant** panel in the sidebar will then display all Ring-related entities from your HA instance.

---

## Docker Images

Pre-built multi-platform images (amd64 + arm64) are published to GitHub Container Registry on every push to `main` and on every version tag:

| Image | Tag |
|---|---|
| `ghcr.io/m4rcelnoel/ring-off-webapp` | `latest`, `1.2`, `1.2.3` |
| `ghcr.io/m4rcelnoel/ring-off-recorder` | `latest`, `1.2`, `1.2.3` |

`docker-compose.yml` pulls `latest` by default. To pin to a specific version replace `latest` with a version tag.

To build from source instead, see the [Development](#development) section.

---

## Troubleshooting

### Quick health check

```bash
docker compose ps                        # all containers should be "Up"
docker compose logs --tail=50 <service>  # check a specific service
```

---

### ring-mqtt cannot connect to the MQTT broker

**Symptom:** Repeated `Unable to connect to MQTT broker` lines in `docker compose logs ring-mqtt`.

**Most common cause (fresh deployment):** ring-mqtt's first-run token setup writes a minimal `config.json` that contains only `ring_token` — `mqtt_url` and other required fields are missing. Since v1.2.1 this is fixed automatically by a startup wrapper, but if you are on an older version you can patch it manually:

```bash
# On the host, in the project directory:
docker exec ring-mqtt cat /data/config.json \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
d.setdefault('mqtt_url', 'mqtt://mosquitto:1883')
d.setdefault('mqtt_options', '')
d.setdefault('enable_cameras', True)
d.setdefault('enable_modes', False)
d.setdefault('enable_panic', False)
d.setdefault('hass_topic', 'homeassistant/status')
d.setdefault('ring_topic', 'ring')
d.setdefault('location_ids', [])
d.setdefault('disarm_code', '')
print(json.dumps(d, indent=2))
" | tee data/ring-mqtt/config.json
docker compose restart ring-mqtt
```

**Check:** After restart you should see `Successfully connected to MQTT broker` in the logs.

---

### ring-mqtt shows `Invalid URL` on startup

**Symptom:** `WARNING - Unhandled Promise Rejection / Invalid URL` in ring-mqtt logs.

**Cause:** Same as above — `mqtt_url` is missing or empty in `data/ring-mqtt/config.json`. Apply the patch above.

---

### Mosquitto fails to write its log file

**Symptom:** `Error: Unable to open log file /mosquitto/log/mosquitto.log for writing` on startup.

**Cause:** The log directory is owned by root on the host but the `mosquitto` user (UID 1883) inside the container cannot write to it.

**Fix (option A — remove file logging, recommended):** Remove the `log_dest file` line from `config/mosquitto.conf`. Docker already captures stdout.

**Fix (option B — fix permissions):**
```bash
sudo chown -R 1883:1883 data/mosquitto-log
docker compose restart mosquitto
```

---

### Cameras do not appear in the dashboard

1. **Check ring-mqtt is connected to the MQTT broker** — see the section above.
2. **Check ring-mqtt is authenticated with Ring:**
   ```bash
   docker compose logs ring-mqtt | grep -E "Ring API|token"
   ```
   You should see `Successfully established connection to Ring API`. If not, the refresh token is expired — log in again via the Ring Off web UI.
3. **Check MQTT topics are being published:**
   ```bash
   docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v -W 10
   ```
   You should see `ring/<location>/camera/<device_id>/...` topics within a few seconds.
4. **Check go2rtc is running:**
   ```bash
   docker compose logs go2rtc
   ```
   Open `http://<host>:1984` — you should see your cameras listed.

---

### No live stream / stream shows a black screen

1. **Check go2rtc can pull the RTSP feed from ring-mqtt:**
   ```bash
   docker compose logs go2rtc | grep -i "error\|rtsp"
   ```
2. **Check RTSP credentials** — `RTSP_USER` and `RTSP_PASS` in `.env` must match your Ring account email and password.
3. **Check go2rtc.yaml has the correct device IDs.** Run the MQTT subscriber above to find your device IDs, then compare with `config/go2rtc.yaml`.
4. **Try the MJPEG fallback** — click the "MJPEG" button on the camera card. If MJPEG works but WebRTC does not, the issue is WebRTC negotiation (often a network/NAT problem between browser and server).

---

### No motion or ding events appearing

1. **Check the recorder is connected to MQTT:**
   ```bash
   docker compose logs recorder | grep -i "mqtt\|error"
   ```
2. **Verify events are published on MQTT:**
   ```bash
   docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v
   # then trigger a motion event or press the doorbell
   ```
3. **Check the webapp WebSocket** — open the browser dev tools Network tab and look for the `/ws/events` WebSocket connection. It should show `OPEN`.

---

### Battery level and WiFi signal not showing on camera cards

**Symptom:** Camera cards appear in the dashboard but the battery and WiFi indicators are missing.

**Cause (pre-1.2.2):** `device_id` was extracted from go2rtc's active `producers` list, which is only populated while someone is actively streaming. On a fresh page load with no active stream, `producers` was empty and `device_id` was `null` for every camera.

**Fix:** Update to v1.2.2 or later. If running an older version, ensure your cameras have published at least one MQTT `info/state` message and that a stream was started at least once to warm up the producers list.

---

### Recordings are not being saved

1. **Check the recorder logs:**
   ```bash
   docker compose logs recorder
   ```
2. **Check disk space** on the recordings volume.
3. **Verify the `VIDEO_PATH` volume is writable** — the recorder container must be able to write to `/videos`.

---

### Push notifications are not delivered

1. **Verify the notification URL in Settings** — ntfy.sh topics must be reachable from the server (not just the browser). Test with:
   ```bash
   docker exec ring-webapp curl -s -o /dev/null -w "%{http_code}" \
     -d "test" https://ntfy.sh/your-topic
   ```
   A `200` response means the server can reach ntfy.sh.
2. **Check the webapp logs** for any HTTP errors when events fire:
   ```bash
   docker compose logs webapp | grep -i "notif\|error"
   ```

---

## Development

### Build from source (all services)

`docker-compose.yml` uses pre-built images from GHCR. Use the dev override to build locally instead:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

This builds `webapp` and `recorder` from source and tags them as `ring-off-webapp:dev` / `ring-off-recorder:dev`. All other services (`mosquitto`, `ring-mqtt`, `go2rtc`) are unchanged.

### Backend hot-reload

```bash
# Start infrastructure only
docker compose up mosquitto ring-mqtt go2rtc -d

# Run backend with hot-reload
cd webapp
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### Frontend hot-reload

```bash
cd webapp/frontend
npm install
npm run dev   # starts on :5173 with proxy to :8080
```

---

## Mosquitto Configuration

The default `config/mosquitto.conf` allows anonymous connections on the local Docker network.
For a production deployment facing the internet, enable authentication:

```conf
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
```

Generate a password file:

```bash
docker exec ring-mosquitto mosquitto_passwd -c /mosquitto/config/passwd myuser
```

---

## Credits & Open Source Libraries

This project is built on the shoulders of excellent open-source work:

### Core services

| Project | Author | License | Purpose |
|---|---|---|---|
| [ring-mqtt](https://github.com/tsightler/ring-mqtt) | tsightler | MIT | Ring → MQTT bridge + internal RTSP server |
| [go2rtc](https://github.com/AlexxIT/go2rtc) | AlexxIT | MIT | RTSP relay, multi-protocol streaming |
| [Eclipse Mosquitto](https://mosquitto.org) | Eclipse Foundation | EPL-2.0 | MQTT message broker |

### Python backend

| Package | License | Purpose |
|---|---|---|
| [FastAPI](https://fastapi.tiangolo.com) | MIT | Async web framework |
| [uvicorn](https://www.uvicorn.org) | BSD | ASGI server |
| [python-ring-doorbell](https://github.com/python-ring-doorbell/python-ring-doorbell) | LGPL-3.0 | Ring API client & OAuth |
| [httpx](https://www.python-httpx.org) | BSD | Async HTTP client |
| [websockets](https://websockets.readthedocs.io) | BSD | WebSocket client |
| [paho-mqtt](https://eclipse.dev/paho/index.php?page=clients/python/index.php) | EPL-2.0 | MQTT client |
| [docker-py](https://docker-py.readthedocs.io) | Apache-2.0 | Docker SDK for restarting containers |
| [ffmpeg](https://ffmpeg.org) | LGPL/GPL | RTSP → MJPEG transcoding + clip recording |

### Frontend

| Package | License | Purpose |
|---|---|---|
| [React](https://react.dev) | MIT | UI framework |
| [Vite](https://vitejs.dev) | MIT | Build tool |
| [TypeScript](https://www.typescriptlang.org) | Apache-2.0 | Type safety |
| [Tailwind CSS](https://tailwindcss.com) | MIT | Utility-first CSS |
| [Radix UI](https://www.radix-ui.com) | MIT | Headless UI primitives |
| [shadcn/ui](https://ui.shadcn.com) | MIT | Component patterns & styling |
| [lucide-react](https://lucide.dev) | ISC | Icon library |
| [clsx](https://github.com/lukeed/clsx) | MIT | Class name utility |
| [tailwind-merge](https://github.com/dcastil/tailwind-merge) | MIT | Tailwind class deduplication |

---

## License

MIT © 2026 Marcel Gruber

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

---

> **Disclaimer:** This project is not affiliated with, endorsed by, or connected to Ring LLC or Amazon. Ring is a trademark of Ring LLC.
