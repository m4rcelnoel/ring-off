# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
