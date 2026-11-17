# Environment variables

**None are required.** `docker-compose.yml` already sets everything the services need, and there is no `.env` file. This page lists every variable the **webapp** and the **recorder** read, so you know what to change when your setup differs from the default.

## How to set a variable

Add it under the service's `environment:` in `docker-compose.override.yml` (copy it from `docker-compose.override.yml.example`), then recreate the containers:

```yaml
# docker-compose.override.yml
services:
  webapp:
    environment:
      - STREAM_WAKE_TIMEOUT=90
  recorder:
    environment:
      - STREAM_WAKE_TIMEOUT=90
```

```bash
docker compose up -d
```

::: tip Some variables belong to both services
The **Service** column says which container reads a variable. Where both do — `TZ`, `STREAM_WAKE_TIMEOUT`, `MQTT_HOST`, `VIDEO_PATH` and others — set it on both, or the two will disagree.
:::

`TZ` is the one exception: the compose file reads it from your shell or an `.env` file next to it, so `TZ=Europe/Berlin docker compose up -d` also works.

## Commonly changed

| Variable | Service | Default | Description |
|---|---|---|---|
| `TZ` | webapp, recorder | `UTC` | Timezone for clip filenames and logs. Set it to match the UI, e.g. `Europe/Berlin`. |
| `WEBRTC_CANDIDATE_HOST` | webapp | host the browser used | Address browsers use to reach port 8555 for WebRTC. Only needed behind a reverse proxy on another machine — set it to the Docker host's IP. |
| `WEBRTC_PORT` | webapp | `8555` | Published WebRTC port, if you map 8555 to something else on the host. |
| `STREAM_WAKE_TIMEOUT` | webapp, recorder | `60` | Seconds to wait for a camera to start streaming — for the live view, the MJPEG fallback and recordings. Battery doorbells can need over 20 s. |
| `MQTT_HOST` | webapp, recorder | `mosquitto` | MQTT broker host. See [Existing MQTT broker](/guides/mqtt-broker). |
| `MQTT_PORT` | webapp, recorder | `1883` | MQTT broker port. |
| `VIDEO_PATH` | webapp, recorder | `/videos` | Recordings folder **inside** the containers. To move recordings, change the volume instead — see [Recording & NAS](/guides/recording#store-recordings-on-a-nas). |

### `TZ`

Without it, container clocks are UTC, so a clip recorded at 18:42 in Berlin is named `…_164234_ding.mp4`. Set it once in an `.env` file next to `docker-compose.yml`:

```bash
echo "TZ=Europe/Berlin" > .env
docker compose up -d
```

## Stream connections

| Variable | Service | Default | Description |
|---|---|---|---|
| `RTSP_HOST` | webapp, recorder | `ring-mqtt` | How the webapp (MJPEG transcoding) and the recorder reach ring-mqtt's RTSP server. |
| `RTSP_PORT` | webapp, recorder | `8554` | ring-mqtt's RTSP port. |
| `GO2RTC_RTSP_HOST` | webapp | `ring-mqtt` | How **go2rtc** reaches ring-mqtt. Written into `config/go2rtc.yaml`, so it must resolve *inside* the go2rtc container — it stays a service name even when the backend runs on your host. |
| `RTSP_USER` / `RTSP_PASS` | webapp, recorder | — | Fallback credentials, only for setups that configure ring-mqtt's RTSP authentication by hand. **Not** your Ring account login. Normally read from ring-mqtt's `config.json`. |
| `GO2RTC_URL` | webapp | `http://go2rtc:1984` | go2rtc's REST API, used to register cameras and proxy the player. |
| `GO2RTC_WS_URL` | webapp | `ws://go2rtc:1984` | go2rtc's WebSocket API, used for WebRTC signalling. |
| `RING_MQTT_UI_PORT` | webapp | `55123` | ring-mqtt's own web UI port. The setup wizard's health check uses it because it is up before a Ring token exists. |

## Files and paths

| Variable | Service | Default | Description |
|---|---|---|---|
| `RING_MQTT_CONFIG` | webapp, recorder | `/ring-mqtt-data/config.json` | ring-mqtt's config, read for the livestream credentials. |
| `RING_MQTT_STATE` | webapp | next to `RING_MQTT_CONFIG` | ring-mqtt's state file (`ring-state.json`), where the Ring refresh token is written. |
| `SETTINGS_FILE` | webapp, recorder | `/app/data/settings.json` | Settings made in the web UI. The recorder reads it (read-only) for the recording options. |
| `EVENTS_FILE` | webapp | next to `SETTINGS_FILE` | Persisted event feed (`events.json`). |
| `SNAPSHOT_DIR` | webapp | next to `SETTINGS_FILE` | Persisted camera thumbnails (`snapshots/`). |
| `GO2RTC_CONFIG` | webapp | `/config/go2rtc.yaml` | go2rtc's config file, maintained by the webapp. |
| `STATIC_DIR` | webapp | `static` | Built frontend. Skipped when absent, so the backend can run without it in development. |

## Rarely needed

| Variable | Service | Default | Description |
|---|---|---|---|
| `RING_CONTAINER` | webapp | `ring-mqtt` | Container to restart after a Ring sign-in — only used if you mount the Docker socket. See [Docker socket](/configuration/ports#docker-socket). |
| `GO2RTC_CONTAINER` | webapp | `ring-go2rtc` | Container to restart when a camera appears — only used if you mount the Docker socket. |
| `APP_VERSION` | webapp | from the image | Overrides the version shown in the UI and sent to Ring. Normally written into the image at build time. |

::: info ring-mqtt itself
ring-mqtt is configured through `data/ring-mqtt/config.json`, not through these variables. Ring Off's init script (`config/ring-mqtt-init.sh`) fills in missing fields on every start. To point ring-mqtt at another broker, see [Existing MQTT broker](/guides/mqtt-broker).
:::
