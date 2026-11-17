# Architektur

Ring Off ist ein kleiner Stack aus Containern. Nur die Weboberfläche und der WebRTC-Port sind nach außen freigegeben, alles andere läuft über das Docker-Netzwerk.

```
                       Browser  (Desktop oder Handy)
                          │                    │
             UI, API, WebSockets          WebRTC-Video
                 Port 8080              Port 8555 tcp+udp
                          │                    │
┌─ Docker-Netzwerk ───────┼────────────────────┼─────────────────────────┐
│                         ▼                    ▼                         │
│          ┌─────────────────────────┐  ┌─────────────────────────┐      │
│          │ webapp            8080  │─▶│ go2rtc            1984  │      │
│          │ FastAPI + React-UI      │ a│ Live-Stream-Relay       │      │
│          └──┬───────────────────┬──┘  └────────────┬────────────┘      │
│             │ b                 │ c                │ RTSP              │
│             ▼                   ▼                  ▼                   │
│  ┌──────────────────┐   ┌─────────────────────────────────────────┐    │
│  │ mosquitto  1883  │◀──│ ring-mqtt                         8554  │    │
│  │ MQTT-Broker      │   │ Ring ↔ MQTT-Brücke + RTSP-Server        │    │
│  └────────┬─────────┘   └────────────────────▲────────────────┬───┘    │
│           │ MQTT                             │ RTSP           │        │
│           ▼                                  │                │        │
│  ┌───────────────────────────────────────────┴───┐            │        │
│  │ recorder   ffmpeg-Clips bei Bewegung/Klingeln │            │        │
│  └───────────────────────────────────────────────┘            │        │
└───────────────────────────────────────────────────────────────┼────────┘
                                                                │ WebRTC / TLS
                                                                ▼
                                                           Ring-Cloud ☁
```

- **a** – WebRTC-Signalisierung und Player-Skript, über die Webapp weitergeleitet
- **b** – Ereignisse und Gerätestatus (MQTT-Abonnement)
- **c** – RTSP für den MJPEG-Fallback, umgewandelt vom ffmpeg der Webapp

## Die Dienste {#the-services}

| Dienst | Image | Aufgabe |
|---|---|---|
| **webapp** | `ghcr.io/m4rcelnoel/ring-off-webapp` | FastAPI-Backend und React-Oberfläche: Dashboard, Einrichtungsassistent, Einstellungen, Ereignisliste, MJPEG-Fallback, Benachrichtigungen |
| **recorder** | `ghcr.io/m4rcelnoel/ring-off-recorder` | Hört auf Bewegung und Klingeln über MQTT und nimmt Clips mit ffmpeg auf |
| **ring-mqtt** | `tsightler/ring-mqtt` | Spricht mit der Ring-Cloud, meldet den Gerätestatus über MQTT und stellt die Kamerabilder per RTSP bereit |
| **go2rtc** | `alexxit/go2rtc` | Leitet die RTSP-Streams als WebRTC oder MSE an den Browser weiter |
| **mosquitto** | `eclipse-mosquitto` | MQTT-Broker, der alles verbindet |

`go2rtc` und `recorder` sind optional – siehe [Optionale Dienste](/de/guide/installation#optional-services).

## Wo deine Daten liegen {#where-your-data-lives}

```
data/                 von git ignoriert
├── ring-mqtt/        config.json (RTSP-Zugangsdaten), ring-state.json (Ring-Token)
├── webapp/           settings.json, events.json, snapshots/
├── videos/           aufgenommene MP4-Clips (oder ein NAS, siehe Aufnahmen & NAS)
└── mosquitto/        Broker-Daten
config/go2rtc.yaml    Kamera-Streams, von der Webapp gepflegt (von git ignoriert)
```

Sichere `data/`, um deine Ring-Anmeldung, Einstellungen und Aufnahmen zu behalten. `config/go2rtc.yaml` wird automatisch aus MQTT neu aufgebaut, falls sie fehlt.

::: warning `config/go2rtc.yaml` nicht committen
Sie enthält die Geräte-IDs deiner Kameras, also Hardware-MAC-Adressen. Deshalb wird sie von git ignoriert.
:::
