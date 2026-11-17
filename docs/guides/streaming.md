# Live streaming

Live streams are served by **go2rtc**, which re-streams ring-mqtt's internal RTSP feeds to the browser.

## How a stream starts

1. You open a camera card. It first shows the latest snapshot.
2. When you start the stream, Ring Off wakes the camera and waits until it actually sends video — up to [`STREAM_WAKE_TIMEOUT`](/configuration/environment#commonly-changed) seconds (60 by default).
3. go2rtc's player negotiates the best transport the browser and network allow: **WebRTC**, then **MSE**, then **MJPEG**.

WebRTC media goes straight from the browser to go2rtc on port **8555** (TCP and UDP). Signalling and the player script go through the webapp on port 8080. See [Ports & security](/configuration/ports).

::: tip MJPEG fallback
Every camera card has an **MJPEG** button. MJPEG is transcoded by the webapp with ffmpeg and only needs port 8080, so it works even when WebRTC can't get through — at the cost of more CPU and no audio.
:::

## Auto-discovery

You normally don't configure anything. Ring Off watches MQTT for cameras and adds each one to `config/go2rtc.yaml` automatically. Start the stack, sign in, and the cameras appear within a few seconds.

To rename or hide a camera, use **Settings → Cameras** — no file editing needed.

## Battery cameras

Battery doorbells sleep to save power and can take 20 seconds or more to send the first frame. Ring Off waits for the camera before handing the stream to go2rtc, and the webapp log shows `Camera <id> awake after …s`.

If a camera regularly needs longer than a minute, raise the timeout for **both** the webapp and the recorder:

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

## Behind a reverse proxy

The browser is told to reach port 8555 on the host name you opened the dashboard with. That works as long as the proxy runs on the same machine as the stack. If it runs on **another** machine, set the Docker host's IP:

```yaml
services:
  webapp:
    environment:
      - WEBRTC_CANDIDATE_HOST=192.168.1.20
```

Port 8555 must be reachable from the browser directly; it is not proxied over HTTP.

## Manual go2rtc entries

Editing `config/go2rtc.yaml` by hand is only for unusual setups, such as streams that point at other hardware. Ring Off leaves entries it did not create alone.

### Finding device IDs

Watch MQTT for a few seconds:

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

Then restart:

```bash
docker compose restart go2rtc webapp
```

::: info Credentials
Leave them out. ring-mqtt's internal RTSP server runs unauthenticated unless `livestream_user` / `livestream_pass` are set in `data/ring-mqtt/config.json` — and if they are, Ring Off fills them into your stream URLs automatically (URL-encoded) and keeps them up to date. They are **not** your Ring account login.
:::

Streams not working? See [No live stream / black screen](/troubleshooting#no-live-stream-black-screen).
