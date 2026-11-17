# Umgebungsvariablen

**Keine davon ist Pflicht.** `docker-compose.yml` setzt bereits alles, was die Dienste brauchen, und es gibt keine `.env`-Datei. Diese Seite listet alle Variablen, die **Webapp** und **Recorder** lesen – damit du weißt, was du ändern musst, wenn dein Aufbau vom Standard abweicht.

## So setzt du eine Variable {#how-to-set-a-variable}

Trage sie unter `environment:` des jeweiligen Dienstes in `docker-compose.override.yml` ein (Vorlage: `docker-compose.override.yml.example`) und erstelle die Container neu:

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

::: tip Manche Variablen gehören zu beiden Diensten
Die Spalte **Dienst** zeigt, welcher Container eine Variable liest. Wo es beide sind – `TZ`, `STREAM_WAKE_TIMEOUT`, `MQTT_HOST`, `VIDEO_PATH` und andere –, setze sie bei beiden, sonst sind sich die zwei uneinig.
:::

`TZ` ist die Ausnahme: Die Compose-Datei liest sie aus deiner Shell oder aus einer `.env` daneben, also funktioniert auch `TZ=Europe/Berlin docker compose up -d`.

## Häufig geändert {#commonly-changed}

| Variable | Dienst | Standard | Beschreibung |
|---|---|---|---|
| `TZ` | webapp, recorder | `UTC` | Zeitzone für Clip-Dateinamen und Logs. Passend zur Oberfläche setzen, z. B. `Europe/Berlin`. |
| `WEBRTC_CANDIDATE_HOST` | webapp | Host, den der Browser benutzt hat | Adresse, über die Browser Port 8555 für WebRTC erreichen. Nur hinter einem Reverse Proxy auf einem anderen Rechner nötig – dann die IP des Docker-Hosts eintragen. |
| `WEBRTC_PORT` | webapp | `8555` | Freigegebener WebRTC-Port, falls du 8555 auf dem Host auf einen anderen Port legst. |
| `STREAM_WAKE_TIMEOUT` | webapp, recorder | `60` | Sekunden, die auf den Stream-Start einer Kamera gewartet wird – für Live-Bild, MJPEG-Fallback und Aufnahmen. Akku-Klingeln brauchen teils über 20 s. |
| `MQTT_HOST` | webapp, recorder | `mosquitto` | Host des MQTT-Brokers. Siehe [Eigener MQTT-Broker](/de/guides/mqtt-broker). |
| `MQTT_PORT` | webapp, recorder | `1883` | Port des MQTT-Brokers. |
| `VIDEO_PATH` | webapp, recorder | `/videos` | Aufnahmeordner **innerhalb** der Container. Um Aufnahmen woanders abzulegen, änderst du stattdessen das Volume – siehe [Aufnahmen & NAS](/de/guides/recording#store-recordings-on-a-nas). |

### `TZ` {#tz}

Ohne sie laufen die Container-Uhren auf UTC, und ein Clip von 18:42 Uhr in Berlin heißt `…_164234_ding.mp4`. Setze sie einmal in einer `.env` neben `docker-compose.yml`:

```bash
echo "TZ=Europe/Berlin" > .env
docker compose up -d
```

## Stream-Verbindungen {#stream-connections}

| Variable | Dienst | Standard | Beschreibung |
|---|---|---|---|
| `RTSP_HOST` | webapp, recorder | `ring-mqtt` | Wie Webapp (MJPEG-Umwandlung) und Recorder den RTSP-Server von ring-mqtt erreichen. |
| `RTSP_PORT` | webapp, recorder | `8554` | RTSP-Port von ring-mqtt. |
| `GO2RTC_RTSP_HOST` | webapp | `ring-mqtt` | Wie **go2rtc** ring-mqtt erreicht. Wird in `config/go2rtc.yaml` geschrieben und muss daher *im* go2rtc-Container auflösbar sein – bleibt also ein Dienstname, auch wenn das Backend direkt auf deinem Rechner läuft. |
| `RTSP_USER` / `RTSP_PASS` | webapp, recorder | – | Ersatz-Zugangsdaten, nur für Setups mit von Hand eingerichteter RTSP-Anmeldung bei ring-mqtt. **Nicht** deine Ring-Zugangsdaten. Normalerweise aus der `config.json` von ring-mqtt gelesen. |
| `GO2RTC_URL` | webapp | `http://go2rtc:1984` | REST-API von go2rtc, um Kameras einzutragen und den Player weiterzuleiten. |
| `GO2RTC_WS_URL` | webapp | `ws://go2rtc:1984` | WebSocket-API von go2rtc für die WebRTC-Signalisierung. |
| `RING_MQTT_UI_PORT` | webapp | `55123` | Port der eigenen Weboberfläche von ring-mqtt. Die Prüfung im Einrichtungsassistenten nutzt ihn, weil er schon vor dem Ring-Token erreichbar ist. |

## Dateien und Pfade {#files-and-paths}

| Variable | Dienst | Standard | Beschreibung |
|---|---|---|---|
| `RING_MQTT_CONFIG` | webapp, recorder | `/ring-mqtt-data/config.json` | Config von ring-mqtt, aus der die Livestream-Zugangsdaten gelesen werden. |
| `RING_MQTT_STATE` | webapp | neben `RING_MQTT_CONFIG` | Zustandsdatei von ring-mqtt (`ring-state.json`), in die der Ring-Refresh-Token geschrieben wird. |
| `SETTINGS_FILE` | webapp, recorder | `/app/data/settings.json` | Einstellungen aus der Weboberfläche. Der Recorder liest sie (nur lesend) für die Aufnahmeoptionen. |
| `EVENTS_FILE` | webapp | neben `SETTINGS_FILE` | Gespeicherte Ereignisliste (`events.json`). |
| `SNAPSHOT_DIR` | webapp | neben `SETTINGS_FILE` | Gespeicherte Vorschaubilder der Kameras (`snapshots/`). |
| `GO2RTC_CONFIG` | webapp | `/config/go2rtc.yaml` | Config-Datei von go2rtc, von der Webapp gepflegt. |
| `STATIC_DIR` | webapp | `static` | Gebautes Frontend. Wird übersprungen, wenn es fehlt, damit das Backend in der Entwicklung auch ohne läuft. |

## Selten nötig {#rarely-needed}

| Variable | Dienst | Standard | Beschreibung |
|---|---|---|---|
| `RING_CONTAINER` | webapp | `ring-mqtt` | Container, der nach einer Ring-Anmeldung neu gestartet wird – nur, wenn du den Docker-Socket einbindest. Siehe [Docker-Socket](/de/configuration/ports#docker-socket). |
| `GO2RTC_CONTAINER` | webapp | `ring-go2rtc` | Container, der bei einer neuen Kamera neu gestartet wird – nur mit eingebundenem Docker-Socket. |
| `APP_VERSION` | webapp | aus dem Image | Überschreibt die Version, die in der Oberfläche angezeigt und an Ring gesendet wird. Wird normalerweise beim Bauen ins Image geschrieben. |

::: info ring-mqtt selbst
ring-mqtt wird über `data/ring-mqtt/config.json` konfiguriert, nicht über diese Variablen. Das Init-Skript von Ring Off (`config/ring-mqtt-init.sh`) ergänzt fehlende Felder bei jedem Start. Wie du ring-mqtt auf einen anderen Broker zeigst, steht unter [Eigener MQTT-Broker](/de/guides/mqtt-broker).
:::
