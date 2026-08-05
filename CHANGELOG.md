# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-08-05

### Upgrading

**Update `docker-compose.yml` — new images alone are not enough.** Three changes live there, and skipping them leaves live video broken:

- go2rtc now mounts the `config` **directory** (`./config:/config:ro`) instead of the single `go2rtc.yaml` file, so a missing file no longer makes Docker create a directory in its place
- port 8555 is published as **both TCP and UDP** for WebRTC; only TCP was mapped before
- `RTSP_USER` / `RTSP_PASS` are gone from the service environments

```bash
git pull && docker compose up -d
```

**Delete `rtsp: listen: ':8555'` from `config/go2rtc.yaml` if it is there.** That line came from the old example, collides with go2rtc's WebRTC port and stops the WebRTC TCP listener from binding. Existing files are not rewritten automatically. Confirm with `docker compose logs go2rtc`, which should show both a `[webrtc] listen tcp` and a `[webrtc] listen udp` line.

`.env` is no longer read and can be deleted. Stream URLs holding `${RTSP_USER}` placeholders are repaired on start, and installs that already work skip the new setup wizard.

### Added
- **Guided setup wizard** — first run is now a walkthrough at `:8080` instead of a README checklist across two ports. It checks the services it depends on (naming the fix for each failure, and treating go2rtc and the recordings folder as optional), takes the Ring sign-in including 2FA, shows devices arriving over MQTT live, and lets each camera be named and switched on or off. Installs that were already working are adopted on startup so upgrading users are not sent back through onboarding; "Run setup again" in Settings replaces the old "Re-authenticate with Ring" button, which was wired to a flag nothing read and did nothing when clicked.
- **Camera names** — cameras can be given a real name instead of the generated `Camera 169F41`, both during setup and afterwards from **Settings → Cameras**, so changing a name never means re-running the wizard. The name is stored separately from the go2rtc stream id, so non-ASCII names survive: "Haustür" displays as written while the stream is `haustur`. Renaming re-registers the stream through go2rtc's API without a restart and the dashboard updates immediately; a camera switched off stays off rather than being re-added by auto-discovery on the next MQTT message.
- **Test notifications** — a "Send a test notification" button in the wizard and a shared delivery helper that returns the real HTTP status. A wrong ntfy or Gotify URL now says so on screen instead of failing into a log line nobody reads, which previously meant discovering it only when a real event was missed.
- **Test suite and CI gate** — 114 tests covering MQTT topic handling, go2rtc config generation and repair, RTSP URL construction, Ring token storage, settings validation, recordings path traversal and the auth middleware. They need no Docker, broker or Ring account. The build workflow now runs them, plus a frontend typecheck, before any image is published.

### Fixed
- **"Notify on connection lost" never fired** — the MQTT handler matched a six-segment topic ending in `availability`, but ring-mqtt publishes device availability to `${deviceTopic}/status`, which has five segments and ends in `status` (`devices/base-ring-device.js`). The branch was unreachable, so a device going offline produced no alert and `_device_availability` stayed empty. Found by the new test suite on its first run.
- **ring-mqtt crash-looped on every fresh deployment** — ring-mqtt 5.9.3 refuses to start when `/data/config.json` is absent ("No configuration file found… shutting down container"), and nothing in the project ever created it. The container therefore restarted forever, and the token setup UI on `:55123` — the very thing the README sends you to in order to produce that file — never came up. `config/ring-mqtt-init.sh` now writes a complete default config when none exists, using ring-mqtt's own schema.
- **The in-app Ring login never actually authenticated ring-mqtt** — `save_ring_token()` wrote the refresh token to `config.json`, but ring-mqtt reads it from `ring-state.json` (`lib/state.js` → `lib/ring.js`); `config.json` has no `ring_token` field at all. Signing in through the web UI appeared to succeed and flipped `ring_configured` to true, so the dashboard loaded — while ring-mqtt kept reporting "No refresh token was found" and no cameras ever appeared. The token is now written to the state file in ring-mqtt's schema, and `/api/status` reports on that file.
- **A failed 2FA code discarded the login session** — `/api/auth/ring/verify` popped the pending session before using it, so a mistyped verification code (or any error while saving the token) forced the user back to re-entering their email and password. The session is now kept until verification actually succeeds.
- **The `<video-rtc>` element was never registered** — `useVideoRtc` injected go2rtc's `video-rtc.js` as a script tag and then polled `customElements.get('video-rtc')` forever. That file only *exports* the `VideoRTC` class; the `customElements.define()` call lives in go2rtc's separate `video-stream.js`. The element therefore never registered, `rtcReady` never became true, and every camera silently rendered the MJPEG fallback instead — WebRTC never ran at all. The module is now imported and the element registered explicitly.
- **The stream URL was set as an attribute the player ignores** — `VideoRTC` starts its connection from a `set src()` property accessor and defines no `attributeChangedCallback`, but React 18 writes unknown custom-element props as attributes. The setter never ran, `wsURL` stayed undefined, and `onconnect()` returned early on every attempt. `src` is now assigned as a property via a ref.
- **Live video was always a black screen** — the `/ws/video` proxy forwarded the browser→go2rtc direction with `websocket.iter_bytes()`, but go2rtc's signaling protocol is JSON *text* frames. Starlette raises on a text message there, the bare `except` swallowed it, and the browser's WebRTC offer never reached go2rtc, so no stream was ever negotiated. The proxy now forwards whichever frame type actually arrives; verified by driving it with a real signaling exchange and receiving fMP4 media back.
- **go2rtc had no WebRTC TCP listener** — `config/go2rtc.yaml.example` set `rtsp: listen: ':8555'`, which collides with go2rtc's default WebRTC port. The TCP listener therefore failed to bind, leaving only a UDP candidate advertising the container's internal Docker IP, which no browser can reach. go2rtc's RTSP server now stays on its default port (unpublished — nothing needs it) and `:8555` is declared for WebRTC. `docker-compose.yml` publishes it as both TCP and UDP; previously only TCP was mapped, so even a working WebRTC setup could not use UDP.
- **The events WebSocket leaked a connection on every unmount** — the cleanup in `useEvents` cleared the reconnect timer before calling `ws.close()`, but `onclose` runs afterwards and scheduled a fresh 3-second reconnect that nothing cancelled. Each unmount left an orphaned socket reconnecting forever, two per React StrictMode double-mount in development.
- **Live events never reached the browser** — `broadcast()` performed an augmented assignment (`ws_clients -= dead`) on a module-level name, which made `ws_clients` a function local and raised `UnboundLocalError` on the loop above it, on every single call. Because the coroutine was only ever scheduled via `asyncio.run_coroutine_threadsafe()` and the resulting future was never awaited, the exception was swallowed silently. Motion/doorbell toasts and live battery/WiFi updates therefore never arrived — the dashboard only ever showed the snapshot of state sent when the WebSocket connected, so a page reload made it look like it worked. Background coroutines scheduled from the MQTT thread now log their failures instead of discarding them.
- **RTSP credentials came from the wrong place, in a form that could not work** — the webapp and recorder read `livestream_user`/`livestream_pass` from ring-mqtt's `config.json`, but go2rtc received `${RTSP_USER}`/`${RTSP_PASS}` from `.env`, and auto-discovery wrote those placeholders into `go2rtc.yaml`. The documented values (Ring account email and password) were never the credentials ring-mqtt's RTSP server expects — and an email address in the userinfo puts a second `@` in the URL, making it unparseable for both ffmpeg and go2rtc. All stream URLs are now built from ring-mqtt's own credentials with percent-encoding, omitting authentication entirely when ring-mqtt has none configured. Existing `go2rtc.yaml` entries, including ones still holding `${RTSP_USER}` placeholders, are repaired automatically on start and whenever the dashboard loads.
- **MJPEG fallback returned 404 whenever it was actually needed** — `/stream/{name}` resolved the device id only from go2rtc's `producers` list, which is empty unless the stream is already being viewed (go2rtc opens RTSP connections lazily). This is the same root cause fixed for `/api/cameras` in 1.2.2, which was never applied here. Both paths now share one `go2rtc.yaml` lookup, with producers kept as a fallback.
- **The backend could not start outside Docker** — `main.py` mounted `static/` unconditionally, a directory that only exists in the built image. Running `uvicorn main:app --reload` for backend development (as documented in the README) crashed on import, and because the reloader keeps the port bound, the vite dev proxy reported `ECONNREFUSED` rather than anything pointing at the real cause. The mount is now skipped when the directory is absent, and its location is overridable via `STATIC_DIR`.
- **A missing `config/go2rtc.yaml` broke go2rtc confusingly** — the file was bind-mounted individually, so if it had not been copied from the `.example` first, Docker silently created a *directory* in its place. go2rtc now mounts the `config` directory, and the webapp creates `go2rtc.yaml` on first start if it is absent.

### Added
- **`GO2RTC_RTSP_HOST`** — how go2rtc reaches ring-mqtt's RTSP server, separate from `RTSP_HOST`, which is how the webapp reaches it for its own MJPEG transcoding. They are identical in Docker (`ring-mqtt`) and differ only when the backend runs on the host for development, where writing `localhost` into `go2rtc.yaml` would point go2rtc at itself and produce a black screen. Existing entries naming either host are corrected automatically.
- **`webapp/dev.sh`** — runs the backend against the repository's own `config/` and `data/` directories instead of the container paths compiled into `main.py`, so the documented hot-reload workflow works without hand-exporting six environment variables.

### Changed
- **New cameras no longer restart go2rtc** — auto-discovery registers the stream through go2rtc's REST API, so adding a camera no longer drops everyone currently watching one. A container restart remains as a fallback if the API call fails.
- **`.env` is gone** — it only ever held `RTSP_USER`/`RTSP_PASS`, which are now sourced from ring-mqtt. `.env.example` has been removed and the Quick Start is two steps shorter: there are no config files to copy before the first `docker compose up`. Both variables are still honoured as an explicit fallback for hand-configured RTSP authentication.
- `config/go2rtc.yaml.example` ships with an empty `streams:` map — the previous placeholder entry produced a permanently broken camera card on every fresh install.

## [1.2.5] - 2026-04-03

### Fixed
- **go2rtc health check failing** — the health check used `wget`, which is not available in the `alexxit/go2rtc` image. Replaced with `nc -z 127.0.0.1 1984` (netcat TCP check) which works in the Alpine-based image.

### Documentation
- **Initial Ring authentication documented** — Quick Start now has an explicit step 4 to authenticate ring-mqtt via its web UI at `:55123` before opening the Ring Off dashboard at `:8080`. Added a dedicated troubleshooting entry for the "no refresh token" case with the correct port.
- **RTSP credentials must be set before starting** — Quick Start step 2 now explicitly instructs users to fill in `RTSP_USER` / `RTSP_PASS` in `.env` with their Ring account email and password. Previously the step said "you can leave it empty for now", which caused streams to fail silently. The `.env.example` comment has been corrected to match.

## [1.2.4] - 2026-04-03

### Fixed
- **Auto-discovery never ran on startup** — camera discovery was only triggered inside the `motion`/`ding` MQTT event handler, meaning cameras were never added to `go2rtc.yaml` until a motion or doorbell event fired. ring-mqtt publishes `info/state` for every camera immediately when it connects to the broker; auto-discovery now also runs there (cameras only, not chimes), so streams are configured as soon as ring-mqtt starts.

## [1.2.3] - 2026-04-03

### Added
- **Docker Compose profiles** — `go2rtc` and `recorder` are now optional. Use `--profile streaming` for live video, `--profile recording` for clip saving, or `--profile full` for everything. A plain `docker compose up` starts only the core stack (mosquitto, ring-mqtt, webapp).
- **Health checks** — mosquitto now has a proper health check (`mosquitto_sub` on `$SYS/#`); go2rtc checks its REST API endpoint. `ring-mqtt` and downstream services wait for `service_healthy` before starting, eliminating the startup race condition where ring-mqtt tried to connect before mosquitto was ready.

### Fixed
- **"Using an Existing MQTT Broker" documentation was incorrect** — the section told users to set `MQTTHOST`/`MQTTPORT` environment variables on ring-mqtt, but ring-mqtt's Docker mode ignores these variables entirely. Corrected to show how to set `mqtt_url` directly in `data/ring-mqtt/config.json`, including examples for authenticated and TLS brokers.

## [1.2.2] - 2026-04-03

### Fixed
- **Battery and WiFi info never showing on camera cards** — `/api/cameras` was extracting `device_id` from go2rtc's active `producers` list, which is only populated while a stream is actively being viewed (go2rtc uses lazy RTSP connections). On a freshly loaded dashboard with no active stream, `producers` was always empty, `device_id` was `null` for every camera, and `cameraDeviceState()` returned `undefined` — so battery level, WiFi signal, and signal strength were never rendered. Fixed by parsing `go2rtc.yaml` directly to extract device IDs, with active producers kept as a fallback.

## [1.2.1] - 2026-04-03

### Fixed
- **ring-mqtt MQTT broker connection failure on fresh deployments** — ring-mqtt's first-run token setup (port 55123) writes a minimal `config.json` containing only `ring_token`, omitting `mqtt_url` and other required fields. This caused an `Invalid URL` error in ring-mqtt's `Config.init` and prevented it from ever connecting to the Mosquitto broker. A startup wrapper script (`config/ring-mqtt-init.sh`) now patches `config.json` with the correct defaults before ring-mqtt starts, without affecting any existing values.
- **Mosquitto log file error on startup** — removed `log_dest file` directive from `mosquitto.conf`; Docker captures stdout already, so the log volume mount is no longer needed.

## [1.2.0] - 2026-03-18

### Added
- **Low battery notifications** — push alert when a device battery drops below a configurable threshold (default 20%); alert resets automatically once the battery recovers
- **Connection lost notifications** — push alert when a device goes offline (via ring-mqtt availability topic); re-fires only after the device reconnects and drops again
- Both alerts use the existing ntfy.sh / Gotify notification URL and are individually toggleable in Settings

## [1.1.0] - 2026-03-16

### Added
- **Snapshot preview** — MJPEG placeholder thumbnail shown on camera card before stream starts (sourced from ring-mqtt MQTT binary JPEG topic `ring/.../snapshot/image`)
- **Person detection** — motion events with a detected person show a distinct "person" badge and icon in the event feed and toast notifications (from `motion/attributes` MQTT topic)
- **Clip retention policy** — configurable auto-delete of old recordings (default 30 days); hourly background cleanup in the recorder container; set to 0 to keep indefinitely
- **Recordings browser** — new "Recordings" tab in sidebar; lists all clips with camera name, timestamp, and size; click to play inline; delete clips directly from the UI
- **Auto-discovery of cameras** — webapp watches for new device IDs in MQTT topics; automatically appends them to `config/go2rtc.yaml` and restarts go2rtc (no manual config required for new cameras)
- **Push notifications** — send motion/ding alerts via ntfy.sh or Gotify; configure URL and per-event-type toggles in Settings
- **App-level password protection** — optional bcrypt password stored in settings; session cookie auth; login screen shown before Ring credentials; manage via Settings panel
- **WebRTC streaming** — camera streams now use go2rtc's `video-rtc.js` WebRTC custom element for low-latency playback; MJPEG fallback button retained for compatibility
- **Range request support** — recording playback supports HTTP Range headers for video scrubbing
- **`/api/snapshot/{device_id}`** — serve latest JPEG snapshot from MQTT memory
- **`/api/recordings`** — list all recorded clips
- **`GET /recordings/files/{device_id}/{filename}`** — serve video files with Range support
- **`DELETE /api/recordings/{device_id}/{filename}`** — delete individual clips
- **`/api/app/status`**, **`/api/app/login`**, **`/api/app/logout`**, **`/api/app/set-password`** — app auth endpoints
- `pyyaml` and `bcrypt` added to webapp dependencies

### Changed
- `docker-compose.yml`: webapp now mounts `./config` (writable, for auto-discovery) and `./data/videos` (recordings browser); added `GO2RTC_CONFIG`, `GO2RTC_CONTAINER`, `VIDEO_PATH` env vars
- Settings panel expanded with retention, notifications, and app password sections
- Sidebar replaced single Events panel with a tabbed Events / Recordings / HA layout
- Event objects now include `person_detected: bool`
- `/api/cameras` response includes `has_snapshot` field
- Version bumped to 1.1.0

## [1.0.0] - 2026-03-16

### Added
- **Live camera streaming** via MJPEG over ffmpeg — works with a plain `<img>` tag, no plugin required
- **Motion & ding event detection** via MQTT subscription to ring-mqtt topics
- **Local video recording** on motion/ding events using ffmpeg (configurable duration, per-event-type toggle)
- **Device status panel** — battery level and WiFi signal strength for cameras; WiFi signal for chimes
- **Chime device listing** — all Ring Chime devices shown with firmware and network info
- **Real-time WebSocket feed** — events and device state pushed to all connected browsers instantly
- **Ring OAuth login** built into the web UI with 2FA support — no config file editing required
- **Settings panel** — toggle motion/ding recording, set clip duration, configure Home Assistant
- **Home Assistant integration** — browse and display Ring-related HA entities from the web UI
- **go2rtc proxy** — HTTP and WebSocket proxy endpoints for the go2rtc RTSP relay
- **Multi-service Docker Compose stack**: mosquitto, ring-mqtt, go2rtc, webapp, recorder
- **Multi-stage Docker build** — Node 20 builds React frontend, Python 3.11 serves it
- **Multi-platform Docker images** (linux/amd64, linux/arm64) via GitHub Actions
