# Ring Off

Self-hosted Ring doorbell management: live camera streams, motion & doorbell event recording, battery/WiFi monitoring — all without a Ring subscription.

> **No cloud. No subscription. Your data stays at home.**

![Ring Off Web Interface](image/webinterface.png)

---

## Tested Hardware

| Device | Status |
|---|---|
| Ring Video Doorbell 3 | ✅ Tested |
| Ring Video Doorbell (2nd Gen) | ✅ Reported working by a user |

Other Ring cameras that work with [ring-mqtt](https://github.com/tsightler/ring-mqtt) should work too — battery cameras, wired doorbells, and indoor/outdoor cameras. If you've tested another model, feel free to open a PR.

---

## Features

- **Live streams** — go2rtc's player negotiates WebRTC, MSE or MJPEG automatically, whichever the browser and network allow
- **Snapshot previews** — camera cards show the latest JPEG thumbnail before you start a stream, sized to each camera's own aspect ratio
- **Person detection** — motion events with an identified person get a distinct badge in the event feed
- **Motion & ding recording** — clips saved locally on every event, configurable per type and duration
- **Recordings browser** — browse, play, and delete clips from the sidebar (bottom bar on phones)
- **Clip retention policy** — auto-delete recordings older than a configurable number of days
- **Push notifications** — ntfy.sh and Gotify support; per-event-type toggles for motion, ding, low battery, and connection lost
- **Auto-discovery** — new cameras found in MQTT are automatically added to go2rtc (no manual config)
- **Password protection** — optional app-level login screen with bcrypt-hashed password
- **Real-time event feed** — motion and doorbell events pushed instantly via WebSocket
- **Device status** — battery level and WiFi signal for cameras; WiFi signal for chimes
- **Ring login in the UI** — OAuth2 with 2FA support, no manual config file editing
- **Home Assistant panel** — browse Ring-related HA entities directly from the dashboard
- **NAS-ready** — point the recordings folder at your NAS with a two-line override
- **Works on phones** — responsive layout with a bottom navigation bar
- **Multi-arch Docker images** — runs on x86-64 and Raspberry Pi (arm64)

---

## Architecture

```
                       Browser  (desktop or phone)
                          │                    │
             UI, API, WebSockets          WebRTC media
                 port 8080              port 8555 tcp+udp
                          │                    │
┌─ Docker network ────────┼────────────────────┼─────────────────────────┐
│                         ▼                    ▼                         │
│          ┌─────────────────────────┐  ┌─────────────────────────┐      │
│          │ webapp            8080  │─▶│ go2rtc            1984  │      │
│          │ FastAPI + React UI      │ a│ live-stream relay       │      │
│          └──┬───────────────────┬──┘  └────────────┬────────────┘      │
│             │ b                 │ c                │ RTSP              │
│             ▼                   ▼                  ▼                   │
│  ┌──────────────────┐   ┌─────────────────────────────────────────┐    │
│  │ mosquitto  1883  │◀──│ ring-mqtt                         8554  │    │
│  │ MQTT broker      │   │ Ring ↔ MQTT bridge + RTSP server        │    │
│  └────────┬─────────┘   └────────────────────▲────────────────┬───┘    │
│           │ MQTT                             │ RTSP           │        │
│           ▼                                  │                │        │
│  ┌───────────────────────────────────────────┴───┐            │        │
│  │ recorder        ffmpeg clips on motion / ding │            │        │
│  └───────────────────────────────────────────────┘            │        │
└───────────────────────────────────────────────────────────────┼────────┘
                                                                │ WebRTC / TLS
                                                                ▼
                                                           Ring cloud ☁

  a  WebRTC signalling and the player script, proxied by the webapp
  b  events and device state (MQTT subscribe)
  c  RTSP for the MJPEG fallback, transcoded by the webapp's ffmpeg

  Only ports 8080 and 8555 are published; everything else stays on the
  Docker network.

Persistent data
  data/                 gitignored
  ├── ring-mqtt/        config.json (RTSP credentials), ring-state.json (Ring token)
  ├── webapp/           settings.json, events.json, snapshots/
  ├── videos/           recorded MP4 clips (or a NAS, see NAS Recording)
  └── mosquitto/        broker persistence
  config/go2rtc.yaml    camera streams, maintained by the webapp (gitignored)
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Docker | 24+ |
| Docker Compose | v2.20+ (plugin) |
| Ring account | any — subscription **not** required |

---

## Quick Start

**1. Clone the repository**

```bash
git clone https://github.com/m4rcelnoel/ring-off.git
cd ring-off
```

**2. Start the stack**

```bash
docker compose up -d
```

> **No config files to copy.** `config/go2rtc.yaml` is created automatically on first start, and cameras are added to it as they are discovered. There is no `.env` to fill in — the RTSP credentials for ring-mqtt's internal stream server are generated by ring-mqtt itself and picked up automatically.

> **Optional services:** `go2rtc` (live streaming) and `recorder` (clip recording) are included by default. To switch one off without editing `docker-compose.yml`, give it an inactive profile in `docker-compose.override.yml`:
>
> ```yaml
> services:
>   recorder:
>     profiles: ["disabled"]
> ```

**3. Open the web UI and follow the setup wizard**

Navigate to **http://\<your-server-ip\>:8080**. The wizard walks you through it:

1. **Checks** — confirms the broker, ring-mqtt, go2rtc and the data folders are healthy, and tells you exactly what to fix if one is not
2. **Ring account** — your email and password, plus a 2FA code if your account uses one
3. **Devices** — cameras and chimes appear here as ring-mqtt announces them
4. **Cameras** — name each one ("Front Door" rather than `Camera 169F41`) and switch off any you do not want
5. **Alerts** — optional clip recording and push notifications, with a button that sends a test and reports what actually happened
6. **Finish** — optionally set a dashboard password

The refresh token is saved to `data/ring-mqtt/ring-state.json`, and ring-mqtt is restarted within a few seconds to load it. You only need to do this once; the token persists across restarts.

Afterwards, **Settings → Cameras** lets you rename a camera or hide it from the dashboard at any time — no need to re-run setup. **Run setup again** in the same panel replays the whole wizard if you want to re-check services or sign in to a different Ring account.

> ring-mqtt also has its own token setup UI on port 55123. You no longer need it, and it is not published because it has no authentication. As a fallback if the in-app login fails, publish it temporarily in `docker-compose.override.yml` (`ring-mqtt: ports: ["55123:55123"]`) and remove it again afterwards.

---

## Updating

```bash
cd ring-off
git pull
docker compose pull
docker compose up -d
```

`git pull` updates the compose file and `config/ring-mqtt-init.sh`; `docker compose pull` fetches the new images. Your data in `data/`, `config/go2rtc.yaml` and the settings made in the web UI are kept — no migration step is needed. Read the **Upgrading** notes in [CHANGELOG.md](CHANGELOG.md) before a minor-version update.

**Keep local changes out of `docker-compose.yml`.** If you edited it (a NAS path, an extra port, an environment variable), `git pull` stops with *"Your local changes … would be overwritten by merge"*. Move those changes into `docker-compose.override.yml` — Compose loads it automatically and git ignores it:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml   # then edit
git checkout -- docker-compose.yml                                   # drop your edits to the original
git pull
```

If you would rather keep your edited file, `git stash && git pull && git stash pop` re-applies your changes on top of the update.

**Installed from a release ZIP instead of git?** Extract the new ZIP into a separate folder and copy over only `docker-compose.yml` and the files in `config/` that it contains — never `data/` or your own `config/go2rtc.yaml`. Keep your own changes in `docker-compose.override.yml` there as well, so the copied `docker-compose.yml` does not undo them.

---

## Stream Setup

Ring camera streams are served by **go2rtc**, which re-streams ring-mqtt's internal RTSP feeds.

> **Auto-discovery (recommended):** Ring Off automatically detects new cameras from MQTT and adds them to `config/go2rtc.yaml`. Just start the stack, log in, and wait a few seconds — cameras will appear without any manual config.

### Manual setup (optional)

To rename a camera or hide it, use **Settings → Cameras** in the web UI — no file editing needed. Editing `config/go2rtc.yaml` by hand is only for unusual setups, such as streams that point at other hardware; Ring Off leaves entries it did not create alone.

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
  front_door: rtsp://ring-mqtt:8554/DEVICE_ID_live
  back_door:  rtsp://ring-mqtt:8554/DEVICE_ID_live
```

> **Credentials:** leave them out. ring-mqtt's internal RTSP server runs unauthenticated unless `livestream_user` / `livestream_pass` are set in `data/ring-mqtt/config.json` — and if they are, Ring Off fills them into your stream URLs automatically (URL-encoded) and keeps them up to date. They are **not** your Ring account login.

> **Privacy note:** `config/go2rtc.yaml` is gitignored because it contains your camera device IDs (hardware MAC addresses). Never commit it — use the `.example` file for version control.

Then restart:

```bash
docker compose restart go2rtc webapp
```

---

## Configuration

### Environment variables

None are required — `docker-compose.yml` sets everything the services need, and there is no `.env` file. To set one, add it under the service's `environment:` in `docker-compose.override.yml`. The RTSP credentials for ring-mqtt's internal stream server are read from `data/ring-mqtt/config.json`, which ring-mqtt manages itself.

These are worth knowing if you deviate from the default compose setup:

| Variable | Default | Description |
|---|---|---|
| `RTSP_HOST` | `ring-mqtt` | How the **webapp** reaches ring-mqtt's RTSP server, for its own MJPEG transcoding |
| `GO2RTC_RTSP_HOST` | `ring-mqtt` | How **go2rtc** reaches it. Written into `config/go2rtc.yaml`, so it must resolve *inside* the go2rtc container — this is why it stays a service name even when the backend runs on your host |
| `RTSP_USER` / `RTSP_PASS` | — | Fallback credentials, only for setups that configure ring-mqtt's RTSP authentication by hand. **Not** your Ring account login |
| `RING_MQTT_CONFIG` | `/ring-mqtt-data/config.json` | ring-mqtt's config, read for the livestream credentials |
| `RING_MQTT_STATE` | alongside the config | ring-mqtt's state file, where the Ring refresh token is written |
| `STATIC_DIR` | `static` | Built frontend. Skipped when absent, so the backend can run without it in development |
| `TZ` | `UTC` | Timezone for clip filenames and logs. Set it to match the UI, e.g. `TZ=Europe/Berlin` |
| `WEBRTC_CANDIDATE_HOST` | the host the browser used | Address browsers use to reach port 8555 for WebRTC. Only needed behind a reverse proxy on another machine |
| `WEBRTC_PORT` | `8555` | Published WebRTC port, if you map 8555 to something else on the host |
| `MQTT_HOST` / `MQTT_PORT` | `mosquitto` / `1883` | Broker for the webapp and recorder — see [Using an Existing MQTT Broker](#using-an-existing-mqtt-broker) |
| `VIDEO_PATH` | `/videos` | Recordings folder inside the webapp and recorder containers |
| `STREAM_WAKE_TIMEOUT` | `60` | Seconds to wait for a camera to start streaming — for the live view, the MJPEG fallback and recordings. Battery doorbells can need over 20 s |
| `EVENTS_FILE` | alongside settings | Persisted event feed |
| `SNAPSHOT_DIR` | alongside settings | Persisted camera thumbnails |

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
| Home Assistant URL / token | — | Enables the HA panel |
| HA entity filter | `ring, doorbell` | Comma-separated terms matched against entity IDs and friendly names |
| Cameras | all shown | Rename cameras or hide them from the dashboard |

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

Only two ports are published. Everything else talks over the Docker network.

| Service | Port | Published | Purpose |
|---|---|---|---|
| webapp | **8080** | yes | Web UI + API |
| go2rtc | **8555** tcp+udp | yes | WebRTC media — the browser connects here directly for live video |
| go2rtc | 1984 | no | go2rtc UI and API; the webapp proxies what it needs |
| mosquitto | 1883 | no | MQTT broker |
| ring-mqtt | 8554 | no | RTSP streams |
| ring-mqtt | 55123 | no | ring-mqtt's own token setup UI — the setup wizard replaces it |

> **8555 needs both protocols.** WebRTC prefers UDP and falls back to TCP; mapping only one leaves browsers unable to connect on networks that block the other.
>
> Ring Off tells the browser to reach 8555 on the same host name you opened the dashboard with. If you access it through a reverse proxy on a *different* machine, set `WEBRTC_CANDIDATE_HOST` on the webapp to the IP of the Docker host.

> **Why the others are closed.** The broker allows anonymous connections and ring-mqtt's setup UI has no authentication at all, so publishing them hands anyone on your network your Ring topics and camera streams. Each is a one-line `ports:` entry in `docker-compose.override.yml` if you need it (see the example file) — put a password on Mosquitto first if you expose 1883 for Home Assistant.

### Docker socket

The webapp does **not** mount `/var/run/docker.sock`. That is root-equivalent access to the host, and this is the container that parses browser input.

It was previously used to restart go2rtc when a camera appeared and ring-mqtt after a Ring sign-in. go2rtc is now updated over its REST API instead, and ring-mqtt is restarted from inside its own container: `config/ring-mqtt-init.sh` watches for the token the wizard writes and restarts ring-mqtt within a few seconds. Note that ring-mqtt, once started without a token, never re-reads its state file on its own.

---

## NAS Recording

To store recordings on a NAS, point **both** the recorder and the webapp at your NAS mount — the recorder writes the clips, the webapp lists, plays and deletes them. If only the recorder moves, clips are saved but the Recordings panel stays empty.

Put this in `docker-compose.override.yml` (copy `docker-compose.override.yml.example`), not in `docker-compose.yml`, so that updates keep working — see [Updating](#updating):

```yaml
services:
  recorder:
    volumes:
      - /mnt/nas/ring-videos:/videos   # ← your NAS mount point
  webapp:
    volumes:
      - /mnt/nas/ring-videos:/videos   # ← the same folder
```

Compose replaces the default `./data/videos:/videos` mount with this one, because both target `/videos`. Existing clips are not moved; copy `data/videos/*` to the NAS folder if you want to keep them.

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

Delete or comment out the entire `mosquitto:` block and remove `mosquitto` from every `depends_on`. This is the one change that cannot live in `docker-compose.override.yml`, because an override cannot remove the `depends_on` entries — update with `git stash && git pull && git stash pop` afterwards (see [Updating](#updating)).

**2. Update ring-mqtt's config to point at your broker**

ring-mqtt in Docker mode reads its MQTT connection from `data/ring-mqtt/config.json`, not from environment variables. Change `mqtt_url` there and keep the other fields (the Ring token lives in `ring-state.json`, not in this file):

```json
{
  "mqtt_url": "mqtt://192.168.1.100:1883"
}
```

For authenticated brokers:

```json
{
  "mqtt_url": "mqtt://myuser:mypassword@192.168.1.100:1883"
}
```

For TLS (port 8883):

```json
{
  "mqtt_url": "mqtts://192.168.1.100:8883"
}
```

**3. Update webapp and recorder environment variables**

```yaml
# docker-compose.override.yml
services:

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

The **HA** panel in the sidebar (bottom bar on phones) then lists matching entities from your HA instance. By default it matches `ring` and `doorbell`; adjust **HA entity filter** in Settings if your entities are named differently, e.g. in another language.

---

## Docker Images

Pre-built multi-platform images (amd64 + arm64) are published to GitHub Container Registry:

| Image | Tags |
|---|---|
| `ghcr.io/m4rcelnoel/ring-off-webapp` | `latest`, `1.4`, `1.4.2`, `staging` |
| `ghcr.io/m4rcelnoel/ring-off-recorder` | `latest`, `1.4`, `1.4.2`, `staging` |

`latest` follows `main`, version tags are fixed releases, and `staging` is the pre-release branch. `docker-compose.yml` pulls `latest`; to pin a version, set `image:` for both services in `docker-compose.override.yml`.

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

**Most common cause (fresh deployment):** ring-mqtt's first-run token setup writes a minimal `config.json` that contains only `ring_token` — `mqtt_url` and other required fields are missing. Since v1.2.1 `config/ring-mqtt-init.sh` adds the missing fields on every start, so a restart repairs it:

```bash
docker compose restart ring-mqtt
```

If it persists, check that `mqtt_url` in `data/ring-mqtt/config.json` points at your broker (`mqtt://mosquitto:1883` for the bundled one).

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

### ring-mqtt restarts in a loop and never comes up

**Symptom:** `No configuration file found at /data/config.json` followed by `A critical error was detected, shutting down container...`, repeating forever. `docker compose ps` shows ring-mqtt as `Restarting`.

**Cause:** ring-mqtt refuses to start without a config file, and on a fresh deployment the `data/ring-mqtt/` volume is empty. The token setup UI on `:55123` — which is what would create that file — cannot come up either, because the container dies first.

**Fix:** Update to 1.3.0 or later, where `config/ring-mqtt-init.sh` writes a complete default config before ring-mqtt starts. On older versions, create `data/ring-mqtt/config.json` by hand with at least `{"mqtt_url": "mqtt://mosquitto:1883", "ring_topic": "ring", "enable_cameras": true}` and restart.

---

### ring-mqtt is waiting for a Ring token (fresh deployment)

**Symptom:** `No refresh token was found in the state file, use the Web UI at http://<host_ip_address>:55123/ to generate a token` in ring-mqtt logs. No cameras appear in the dashboard.

**Cause:** ring-mqtt has never been authenticated with your Ring account. This is expected on a fresh deployment.

**Fix:** Sign in through the Ring Off web UI at `:8080`. It performs the OAuth exchange (including 2FA), writes the refresh token to `data/ring-mqtt/ring-state.json`, and `config/ring-mqtt-init.sh` restarts ring-mqtt within a few seconds so it loads the token. ring-mqtt's own setup UI (port 55123, not published) does the same and remains a fallback — see Quick Start.

> The token goes in **`ring-state.json`**, not `config.json` — ring-mqtt reads it from there and `config.json` has no `ring_token` field at all. Before 1.3.0 the web UI login wrote it to the wrong file, so signing in appeared to succeed while ring-mqtt stayed unauthenticated and no cameras ever appeared.

> You only need to do this once. The token is persisted in the `data/ring-mqtt/` volume and survives container restarts.

---

### Cameras do not appear in the dashboard

1. **Make sure you have authenticated with Ring** — sign in at `http://<host>:8080`. See the section above.
2. **Check ring-mqtt is connected to the MQTT broker** — see the section above.
3. **Check ring-mqtt is authenticated with Ring:**
   ```bash
   docker compose logs ring-mqtt | grep -E "Ring API|token"
   ```
   You should see `Successfully established connection to Ring API`. If not, the refresh token is expired — log in again via the Ring Off web UI.
4. **Check MQTT topics are being published:**
   ```bash
   docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v -W 10
   ```
   You should see `ring/<location>/camera/<device_id>/...` topics within a few seconds.
5. **Check go2rtc knows your cameras:**
   ```bash
   docker exec ring-webapp python -c "import httpx; print(httpx.get('http://go2rtc:1984/api/streams').text)"
   ```
   Each camera should be listed. go2rtc's own UI on port 1984 is not published; add it in `docker-compose.override.yml` if you want to open it in the browser.

---

### No live stream / stream shows a black screen

1. **Check go2rtc can pull the RTSP feed from ring-mqtt:**
   ```bash
   docker compose logs go2rtc | grep -i "error\|rtsp"
   ```
2. **Check the stream URLs in `config/go2rtc.yaml`.** They must match whatever `livestream_user` / `livestream_pass` are in `data/ring-mqtt/config.json` (no credentials at all if those keys are absent). Ring Off rewrites them automatically on start and whenever the dashboard loads — if you see literal `${RTSP_USER}` placeholders, you are on a version older than 1.3.0.

   > **Upgrading from ≤ 1.2.5:** those placeholders came from `.env`, and your Ring account email/password were never the right credentials — an unescaped `@` also made the URL unparseable. Ring Off now repairs existing entries on start, and `.env` is no longer used.
3. **Check go2rtc.yaml has the correct device IDs.** Run the MQTT subscriber above to find your device IDs, then compare with `config/go2rtc.yaml`.
4. **Check the stream host.** Entries must name a host go2rtc itself can resolve — normally `ring-mqtt`. If you see `localhost` there, the file was written by a backend running outside Docker; set `GO2RTC_RTSP_HOST=ring-mqtt` (the default) and restart the webapp, which repairs existing entries automatically.
5. **Check go2rtc kept its WebRTC listener.** `docker compose logs go2rtc` should show **both** lines:
   ```
   [webrtc] listen tcp addr=[::]:8555
   [webrtc] listen udp addr=...:8555
   ```
   If the TCP line is missing, something else in `config/go2rtc.yaml` has taken port 8555 — most often a leftover `rtsp: listen: ':8555'` from a pre-1.3.0 config. Remove it; go2rtc's RTSP server does not need to be reachable and its default port is fine.
6. **Check port 8555 is reachable from the browser.** WebRTC media goes straight from the browser to go2rtc on 8555 (TCP and UDP), at the host name you opened the dashboard with. Behind a reverse proxy on another machine, set `WEBRTC_CANDIDATE_HOST` to the Docker host's IP.
7. **Try the MJPEG fallback** — click the "MJPEG" button on the camera card. If MJPEG works but WebRTC does not, the issue is WebRTC negotiation, usually step 6.
8. **Battery cameras that wake slowly** — some battery doorbells take 20 seconds or more to send the first frame. Ring Off waits for the camera before handing the stream to go2rtc, up to `STREAM_WAKE_TIMEOUT` (60 s by default); the webapp log shows `Camera <id> awake after …s`. If a camera regularly needs longer, raise the variable for the webapp and the recorder.

   > MJPEG is transcoded by the webapp with ffmpeg. The Docker image ships it; if you are running the backend directly on your machine for development and ffmpeg is not installed, `/stream/<name>` returns an empty `200` and the fallback shows nothing.

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
2. **Check the recording settings** — *Record on motion* and *Record on ding* in Settings. The log says `motion recording disabled, skipping` when one is off.
3. **Check disk space** — the recorder stops below 512 MB free on the recordings volume and logs how much is left.
4. **Verify the `VIDEO_PATH` volume is writable** — the recorder container must be able to write to `/videos`. On a NAS, both the recorder and the webapp need the mount (see [NAS Recording](#nas-recording)).
5. **A clip was skipped** — one recording per camera runs at a time; an event during a running clip is skipped. Failed attempts are retried three times and logged with ffmpeg's last error line.

---

### Push notifications are not delivered

1. **Verify the notification URL in Settings** — ntfy.sh topics must be reachable from the server (not just the browser). Test with:
   ```bash
   docker exec ring-webapp python -c "import httpx; print(httpx.post('https://ntfy.sh/your-topic', content=b'test').status_code)"
   ```
   A `200` response means the server can reach ntfy.sh. The setup wizard's **Alerts** step also has a *Send a test notification* button that reports the exact HTTP status (**Settings → Run setup again**).
2. **Check the webapp logs** for any HTTP errors when events fire:
   ```bash
   docker compose logs webapp | grep -i "notif\|error"
   ```

---

## Development

### Branches

Work lands on `staging` first; `main` only ever receives merges from it.

| Branch | CI | Image tag |
|---|---|---|
| `staging` | tests + typecheck, then build | `ghcr.io/…:staging` |
| `main` | tests + typecheck, then build | `ghcr.io/…:main` and `:latest` |
| tag `v*` | — | `:1.4.2`, `:1.4` + GitHub release |

`main` is protected: no direct pushes, and the `Tests` job has to be green before a pull request can be merged. To try a change before it reaches `main`, point the images at `:staging` in `docker-compose.override.yml`:

```yaml
services:
  webapp:   { image: ghcr.io/m4rcelnoel/ring-off-webapp:staging }
  recorder: { image: ghcr.io/m4rcelnoel/ring-off-recorder:staging }
```

### Build from source (all services)

`docker-compose.yml` uses pre-built images from GHCR. Use the dev override to build locally instead:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

This builds `webapp` and `recorder` from source and tags them as `ring-off-webapp:dev` / `ring-off-recorder:dev`. All other services (`mosquitto`, `ring-mqtt`, `go2rtc`) are unchanged.

### Backend hot-reload

```bash
# Start infrastructure only — the dev override publishes its ports on localhost
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d mosquitto ring-mqtt go2rtc

# Run backend with hot-reload
cd webapp
pip install -r requirements.txt
./dev.sh
```

`dev.sh` is a thin wrapper around `uvicorn main:app --reload --port 8080`. It exists because the defaults compiled into `main.py` are container paths (`/config`, `/videos`) and Docker network hostnames (`mosquitto`, `go2rtc`) that do not resolve on a dev machine — it points them at the repository's own `config/` and `data/` directories and at the ports `docker-compose.dev.yml` publishes on localhost (the regular stack publishes none of them). Running `uvicorn` directly still works; you will just see `Could not create /config/go2rtc.yaml` and `MQTT connect failed` on startup, and MQTT-driven features (events, device state, camera discovery) will be inert.

Override any variable by exporting it first, e.g. `PORT=8081 ./dev.sh`.

### Tests

```bash
pip install -r webapp/requirements.txt -r recorder/requirements.txt -r requirements-dev.txt
pytest
```

The suite runs without Docker, a broker or a Ring account: MQTT topic handling is
driven through the real `on_message` callback with a stubbed connection, and every
config path is redirected to a temporary directory. CI runs it, together with a
frontend typecheck, before any image is built.

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
| [docker-py](https://docker-py.readthedocs.io) | Apache-2.0 | Optional container restarts, only if you mount the Docker socket |
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
