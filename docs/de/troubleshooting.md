# Fehlerbehebung

## Schneller Gesundheitscheck {#quick-health-check}

```bash
docker compose ps                        # alle Container sollten "Up" sein
docker compose logs --tail=50 <dienst>   # einen bestimmten Dienst prüfen
```

Der Schritt **Checks** im Einrichtungsassistenten führt dieselben Prüfungen im Browser aus: **Settings → Run setup again**.

## Kameras erscheinen nicht im Dashboard {#cameras-do-not-appear-in-the-dashboard}

1. **Bist du bei Ring angemeldet?** – unter `http://<host>:8080`. Siehe [ring-mqtt wartet auf einen Ring-Token](#ring-mqtt-is-waiting-for-a-ring-token).
2. **Ist ring-mqtt mit dem Broker verbunden?** – siehe [ring-mqtt erreicht den MQTT-Broker nicht](#ring-mqtt-cannot-connect-to-the-mqtt-broker).
3. **Ist ring-mqtt bei Ring angemeldet?**
   ```bash
   docker compose logs ring-mqtt | grep -E "Ring API|token"
   ```
   Dort sollte `Successfully established connection to Ring API` stehen. Wenn nicht, ist der Refresh-Token abgelaufen – melde dich in der Weboberfläche neu an.
4. **Werden MQTT-Topics veröffentlicht?**
   ```bash
   docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v -W 10
   ```
   Innerhalb weniger Sekunden sollten Topics wie `ring/<location>/camera/<device_id>/...` erscheinen.
5. **Kennt go2rtc deine Kameras?**
   ```bash
   docker exec ring-webapp python -c "import httpx; print(httpx.get('http://go2rtc:1984/api/streams').text)"
   ```
   Jede Kamera sollte aufgelistet sein. Die Oberfläche von go2rtc auf Port 1984 ist nicht freigegeben; trag sie in `docker-compose.override.yml` ein, wenn du sie öffnen willst.

## Kein Live-Bild / schwarzer Bildschirm {#no-live-stream-black-screen}

1. **Kann go2rtc den RTSP-Stream von ring-mqtt holen?**
   ```bash
   docker compose logs go2rtc | grep -i "error\|rtsp"
   ```
2. **Stimmen die Stream-URLs in `config/go2rtc.yaml`?** Sie müssen zu `livestream_user` / `livestream_pass` in `data/ring-mqtt/config.json` passen (gar keine Zugangsdaten, wenn diese Schlüssel fehlen). Ring Off schreibt sie beim Start und bei jedem Laden des Dashboards automatisch neu. Stehen dort wörtlich `${RTSP_USER}`-Platzhalter, ist deine Version älter als 1.3.0.
3. **Stimmen die Geräte-IDs?** Starte den MQTT-Abonnenten von oben und vergleiche die IDs mit `config/go2rtc.yaml`.
4. **Stimmt der Stream-Host?** Die Einträge müssen einen Host nennen, den go2rtc selbst auflösen kann – normalerweise `ring-mqtt`. Steht dort `localhost`, wurde die Datei von einem Backend außerhalb von Docker geschrieben; setze `GO2RTC_RTSP_HOST=ring-mqtt` (der Standard) und starte die Webapp neu, sie repariert die Einträge selbst.
5. **Hat go2rtc seinen WebRTC-Listener?** `docker compose logs go2rtc` sollte **beide** Zeilen zeigen:
   ```
   [webrtc] listen tcp addr=[::]:8555
   [webrtc] listen udp addr=...:8555
   ```
   Fehlt die TCP-Zeile, belegt etwas anderes in `config/go2rtc.yaml` Port 8555 – meist ein übrig gebliebenes `rtsp: listen: ':8555'` aus einer Config vor 1.3.0. Entferne es.
6. **Erreicht der Browser Port 8555?** TCP und UDP, unter dem Hostnamen, mit dem du das Dashboard geöffnet hast. Hinter einem Reverse Proxy auf einem anderen Rechner setze [`WEBRTC_CANDIDATE_HOST`](/de/configuration/environment#commonly-changed).
7. **Probier den MJPEG-Knopf** auf der Kamerakarte. Geht MJPEG, aber WebRTC nicht, liegt es an der WebRTC-Aushandlung – meist Schritt 6.
8. **Akku-Kameras, die langsam aufwachen**, brauchen teils 20 s oder mehr bis zum ersten Bild. Im Log der Webapp steht `Camera <id> awake after …s`. Braucht eine Kamera regelmäßig länger, erhöhe [`STREAM_WAKE_TIMEOUT`](/de/guides/streaming#battery-cameras) für Webapp und Recorder.

::: details Update von 1.2.5 oder älter
Die `${RTSP_USER}`-Platzhalter kamen aus der `.env`, und deine Ring-Zugangsdaten waren nie die richtigen – ein nicht maskiertes `@` machte die URL außerdem unlesbar. Ring Off repariert vorhandene Einträge inzwischen beim Start, die `.env` wird nicht mehr verwendet.
:::

## Keine Bewegungs- oder Klingel-Ereignisse {#no-motion-or-ding-events}

1. **Ist der Recorder mit MQTT verbunden?**
   ```bash
   docker compose logs recorder | grep -i "mqtt\|error"
   ```
2. **Kommen Ereignisse über MQTT an?**
   ```bash
   docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v
   # dann Bewegung auslösen oder klingeln
   ```
3. **Steht der WebSocket der Webapp?** In den Entwicklertools des Browsers, Reiter Netzwerk, sollte die WebSocket-Verbindung `/ws/events` den Status `OPEN` haben.

## Aufnahmen werden nicht gespeichert {#recordings-are-not-being-saved}

1. **Log des Recorders prüfen:** `docker compose logs recorder`
2. **Aufnahme-Einstellungen prüfen** – *Record on Motion* und *Record on Doorbell*. Ist eine aus, steht im Log `motion recording disabled, skipping`.
3. **Speicherplatz prüfen** – der Recorder hört unter 512 MB freiem Platz auf dem Aufnahme-Volume auf und schreibt ins Log, wie viel übrig ist.
4. **Ist das Volume beschreibbar?** Der Recorder muss nach `/videos` schreiben können. Bei einem NAS brauchen Recorder und Webapp das Mount – siehe [Aufnahmen & NAS](/de/guides/recording#store-recordings-on-a-nas).
5. **Ein Clip wurde übersprungen** – pro Kamera läuft nur eine Aufnahme; ein Ereignis während einer laufenden Aufnahme wird übersprungen. Fehlgeschlagene Versuche werden dreimal wiederholt und mit der letzten Fehlerzeile von ffmpeg geloggt.

## Push-Benachrichtigungen kommen nicht an {#push-notifications-are-not-delivered}

1. **Erreicht der Server den Dienst?** Die Nachricht kommt vom Server, nicht von deinem Browser:
   ```bash
   docker exec ring-webapp python -c "import httpx; print(httpx.post('https://ntfy.sh/dein-topic', content=b'test').status_code)"
   ```
   `200` heißt, der Server erreicht ntfy.sh. Der Schritt **Alerts** im Assistenten hat einen Testknopf, der den genauen HTTP-Status meldet.
2. **Log der Webapp prüfen** auf HTTP-Fehler, wenn Ereignisse kommen:
   ```bash
   docker compose logs webapp | grep -i "notif\|error"
   ```

## ring-mqtt wartet auf einen Ring-Token {#ring-mqtt-is-waiting-for-a-ring-token}

**Symptom:** `No refresh token was found in the state file, use the Web UI at http://<host_ip_address>:55123/ to generate a token` im Log von ring-mqtt. Es erscheinen keine Kameras.

**Ursache:** ring-mqtt wurde noch nie angemeldet. Bei einer frischen Installation ist das normal.

**Lösung:** Melde dich über die Weboberfläche von Ring Off auf Port 8080 an. Sie erledigt die OAuth-Anmeldung (inklusive Zwei-Faktor-Code), schreibt den Refresh-Token nach `data/ring-mqtt/ring-state.json`, und `config/ring-mqtt-init.sh` startet ring-mqtt innerhalb weniger Sekunden neu, damit er den Token lädt. Das musst du nur einmal machen.

::: info `ring-state.json`, nicht `config.json`
ring-mqtt liest den Token aus der Zustandsdatei; `config.json` hat gar kein Feld `ring_token`. Vor 1.3.0 schrieb die Weboberfläche ihn in die falsche Datei – die Anmeldung schien zu klappen, ring-mqtt blieb aber unangemeldet.
:::

## ring-mqtt erreicht den MQTT-Broker nicht {#ring-mqtt-cannot-connect-to-the-mqtt-broker}

**Symptom:** Immer wieder `Unable to connect to MQTT broker` in `docker compose logs ring-mqtt`.

**Ursache:** Meist eine frische Installation, bei der die erste Token-Einrichtung von ring-mqtt eine minimale `config.json` ohne `mqtt_url` geschrieben hat. Seit 1.2.1 ergänzt `config/ring-mqtt-init.sh` fehlende Felder bei jedem Start, ein Neustart repariert es also:

```bash
docker compose restart ring-mqtt
```

Bleibt der Fehler, prüfe, ob `mqtt_url` in `data/ring-mqtt/config.json` auf deinen Broker zeigt (`mqtt://mosquitto:1883` für den mitgelieferten). Nach dem Neustart sollte `Successfully connected to MQTT broker` erscheinen.

## ring-mqtt meldet `Invalid URL` beim Start {#ring-mqtt-shows-invalid-url-on-startup}

**Symptom:** `WARNING - Unhandled Promise Rejection / Invalid URL` im Log von ring-mqtt.

**Ursache und Lösung:** Wie oben – `mqtt_url` fehlt oder ist leer in `data/ring-mqtt/config.json`. Starte ring-mqtt neu.

## ring-mqtt startet in einer Endlosschleife neu {#ring-mqtt-restarts-in-a-loop}

**Symptom:** `No configuration file found at /data/config.json`, danach `A critical error was detected, shutting down container...`, immer wieder. `docker compose ps` zeigt ring-mqtt als `Restarting`.

**Ursache:** ring-mqtt startet nicht ohne Config-Datei, und bei einer frischen Installation ist das Volume `data/ring-mqtt/` leer.

**Lösung:** Aktualisiere auf 1.3.0 oder neuer – dort schreibt `config/ring-mqtt-init.sh` vor dem Start eine vollständige Standard-Config. Bei älteren Versionen lege `data/ring-mqtt/config.json` von Hand an und starte neu:

```json
{ "mqtt_url": "mqtt://mosquitto:1883", "ring_topic": "ring", "enable_cameras": true }
```

## Mosquitto kann seine Logdatei nicht schreiben {#mosquitto-fails-to-write-its-log-file}

**Symptom:** `Error: Unable to open log file /mosquitto/log/mosquitto.log for writing` beim Start.

**Ursache:** Das Log-Verzeichnis gehört auf dem Host root, der Benutzer `mosquitto` (UID 1883) im Container darf nicht hineinschreiben.

**Lösung A (empfohlen):** Entferne die Zeile `log_dest file` aus `config/mosquitto.conf`. Docker fängt die Ausgabe ohnehin ab.

**Lösung B:** Rechte korrigieren:

```bash
sudo chown -R 1883:1883 data/mosquitto-log
docker compose restart mosquitto
```

## Akku und WLAN fehlen auf den Kamerakarten {#battery-and-wifi-not-showing-on-camera-cards}

**Ursache (vor 1.2.2):** Die Geräte-ID wurde aus den aktiven Producern von go2rtc gelesen, die es nur gibt, solange jemand streamt.

**Lösung:** Auf 1.2.2 oder neuer aktualisieren.

## Immer noch nicht gelöst? {#still-stuck}

[Eröffne ein Issue](https://github.com/m4rcelnoel/ring-off/issues) mit deiner Ring-Off-Version, dem Kameramodell und den passenden Zeilen aus `docker compose logs`.
