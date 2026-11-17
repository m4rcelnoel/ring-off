# Live-Streaming

Das Live-Bild liefert **go2rtc**, das die internen RTSP-Streams von ring-mqtt an den Browser weitergibt.

## So startet ein Stream {#how-a-stream-starts}

1. Du öffnest eine Kamerakarte. Sie zeigt zuerst das letzte Vorschaubild.
2. Startest du den Stream, weckt Ring Off die Kamera und wartet, bis sie wirklich Bild liefert – bis zu [`STREAM_WAKE_TIMEOUT`](/de/configuration/environment#commonly-changed) Sekunden (standardmäßig 60).
3. Der Player von go2rtc handelt die beste Übertragung aus, die Browser und Netz erlauben: **WebRTC**, dann **MSE**, dann **MJPEG**.

WebRTC-Video geht direkt vom Browser zu go2rtc auf Port **8555** (TCP und UDP). Signalisierung und Player-Skript laufen über die Webapp auf Port 8080. Siehe [Ports & Sicherheit](/de/configuration/ports).

::: tip MJPEG als Ausweg
Jede Kamerakarte hat einen **MJPEG**-Knopf. MJPEG wird von der Webapp mit ffmpeg umgewandelt und braucht nur Port 8080 – es funktioniert also auch, wenn WebRTC nicht durchkommt. Dafür kostet es mehr Rechenleistung und hat keinen Ton.
:::

## Automatische Erkennung {#auto-discovery}

Normalerweise musst du nichts einrichten. Ring Off beobachtet MQTT und trägt jede Kamera automatisch in `config/go2rtc.yaml` ein. Stack starten, anmelden – nach wenigen Sekunden sind die Kameras da.

Umbenennen oder ausblenden geht unter **Settings → Cameras**, ganz ohne Dateien zu bearbeiten.

## Akku-Kameras {#battery-cameras}

Akku-Klingeln schlafen, um Strom zu sparen, und brauchen teils 20 Sekunden oder mehr bis zum ersten Bild. Ring Off wartet auf die Kamera, bevor es den Stream an go2rtc übergibt; im Log der Webapp steht dann `Camera <id> awake after …s`.

Braucht eine Kamera regelmäßig länger als eine Minute, erhöhe den Wert für **Webapp und Recorder**:

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

## Hinter einem Reverse Proxy {#behind-a-reverse-proxy}

Der Browser bekommt gesagt, dass er Port 8555 unter dem Hostnamen erreicht, mit dem du das Dashboard geöffnet hast. Das passt, solange der Proxy auf demselben Rechner wie der Stack läuft. Läuft er auf einem **anderen** Rechner, trage die IP des Docker-Hosts ein:

```yaml
services:
  webapp:
    environment:
      - WEBRTC_CANDIDATE_HOST=192.168.1.20
```

Port 8555 muss vom Browser direkt erreichbar sein; er wird nicht über HTTP weitergeleitet.

## go2rtc-Einträge von Hand {#manual-go2rtc-entries}

`config/go2rtc.yaml` von Hand zu bearbeiten ist nur für Sonderfälle gedacht, etwa Streams, die auf andere Hardware zeigen. Einträge, die Ring Off nicht selbst angelegt hat, lässt es in Ruhe.

### Geräte-IDs finden {#finding-device-ids}

Beobachte MQTT für ein paar Sekunden:

```bash
docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v -W 10
```

Achte auf Topics wie:

```
ring/<location-id>/camera/<DEVICE_ID>/motion/state ON
```

Trage jede `<DEVICE_ID>` in `config/go2rtc.yaml` ein:

```yaml
streams:
  haustuer: rtsp://ring-mqtt:8554/DEVICE_ID_live
  garten:   rtsp://ring-mqtt:8554/DEVICE_ID_live
```

Dann neu starten:

```bash
docker compose restart go2rtc webapp
```

::: info Zugangsdaten
Lass sie weg. Der interne RTSP-Server von ring-mqtt läuft ohne Anmeldung, solange in `data/ring-mqtt/config.json` kein `livestream_user` / `livestream_pass` gesetzt ist – und wenn doch, trägt Ring Off sie automatisch (URL-kodiert) in deine Stream-URLs ein und hält sie aktuell. Es sind **nicht** deine Ring-Zugangsdaten.
:::

Kein Bild? Siehe [Kein Live-Bild / schwarzer Bildschirm](/de/troubleshooting#no-live-stream-black-screen).
