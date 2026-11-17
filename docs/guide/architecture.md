# Architecture

Ring Off is a small stack of containers. Only the web UI and the WebRTC media port are published; everything else talks over the Docker network.

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
```

- **a** — WebRTC signalling and the player script, proxied by the webapp
- **b** — events and device state (MQTT subscribe)
- **c** — RTSP for the MJPEG fallback, transcoded by the webapp's ffmpeg

## The services

| Service | Image | Role |
|---|---|---|
| **webapp** | `ghcr.io/m4rcelnoel/ring-off-webapp` | FastAPI backend and React UI: dashboard, setup wizard, settings, event feed, MJPEG fallback, notifications |
| **recorder** | `ghcr.io/m4rcelnoel/ring-off-recorder` | Listens for motion and ding events on MQTT and records clips with ffmpeg |
| **ring-mqtt** | `tsightler/ring-mqtt` | Talks to the Ring cloud, publishes device state on MQTT and serves camera streams over RTSP |
| **go2rtc** | `alexxit/go2rtc` | Relays the RTSP streams to the browser as WebRTC or MSE |
| **mosquitto** | `eclipse-mosquitto` | MQTT broker that connects everything |

`go2rtc` and `recorder` are optional — see [Optional services](/guide/installation#optional-services).

## Where your data lives

```
data/                 gitignored
├── ring-mqtt/        config.json (RTSP credentials), ring-state.json (Ring token)
├── webapp/           settings.json, events.json, snapshots/
├── videos/           recorded MP4 clips (or a NAS, see Recording & NAS)
└── mosquitto/        broker persistence
config/go2rtc.yaml    camera streams, maintained by the webapp (gitignored)
```

Back up `data/` to keep your Ring sign-in, settings and recordings. `config/go2rtc.yaml` is rebuilt automatically from MQTT if it goes missing.

::: warning Don't commit `config/go2rtc.yaml`
It contains your camera device IDs, which are hardware MAC addresses. It is gitignored for that reason.
:::
