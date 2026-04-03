# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.5] - 2026-04-03

### Fixed
- **go2rtc health check failing** — the health check used `wget`, which is not available in the `alexxit/go2rtc` image. Replaced with `nc -z 127.0.0.1 1984` (netcat TCP check) which works in the Alpine-based image.

### Documentation
- **Initial Ring login is required on fresh deployments** — added a prominent note in Quick Start (step 4) and a dedicated troubleshooting entry explaining that ring-mqtt needs a Ring OAuth token before cameras appear. The token is obtained by logging in via the Ring Off web UI at `:8080`; it persists across restarts.

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
