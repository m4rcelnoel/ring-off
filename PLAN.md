# Ring Off — Vorgehensplan (Stand 14.11.2026, Branch `staging`)

## Ausgangslage

- **Stack:** FastAPI-Backend (`webapp/main.py`, ~1700 Zeilen) + React/Vite-Frontend, Recorder (`recorder/recorder.py`, ffmpeg), dazu ring-mqtt, Mosquitto und go2rtc per Docker Compose.
- **`staging`** liegt 2 Commits vor `main` (Security-Härtung, persistente Events/Snapshots, Recorder-Retries). Version steht noch auf 1.3.0, der Abschnitt `[Unreleased]` im CHANGELOG ist schon umfangreich.
- **Tests:** vorher 148 grün. Frontend-`tsc` und `vite build` sauber. CI testet nur das Backend.

## Erledigt in der ersten Session (in 1.4.0 veröffentlicht)

| # | Bug | Schwere |
|---|-----|---------|
| 1 | WebSockets (`/ws/events`, `/ws/video`) waren trotz App-Passwort offen: `BaseHTTPMiddleware` sieht keine WS-Handshakes | **Hoch** |
| 2 | `/proxy/go2rtc/*` ohne Login erreichbar und für alle GET/POST offen → go2rtc-API (`/api/config` mit RTSP-Zugangsdaten, `POST /api/streams`) | **Hoch** |
| 3 | Webapp bekam nie MQTT-Events, wenn der Broker beim Start nicht erreichbar war (`loop_start()` wurde übersprungen) | **Hoch** |
| 4 | Recorder startete zwei ffmpeg pro Kamera (Motion + Ding gleichzeitig, oder während der Retry-Pause) | Mittel |
| 5 | Ein MQTT-Payload, der kein UTF-8 ist, brachte den Recorder zum Absturz | Mittel |
| 6 | Range-Request hinter dem Dateiende → 500 statt 416 | Niedrig |
| 7 | DELETE löschte beliebige Dateien in Kameraordnern (und im Root über `.`) | Mittel |
| 8 | `settings.json`/`events.json` nicht atomar geschrieben (Recorder liest parallel), kaputte Settings blockierten den Start | Mittel |
| 9 | `src` im Video-WS wurde ungeprüft in die Upstream-URL übernommen | Niedrig |

Dazu 21 Regressionstests (`tests/test_security.py`, Ergänzungen in `test_recorder.py` und `test_mqtt.py`). Alle neuen Tests schlagen auf dem alten Code fehl und laufen jetzt durch: **169 grün**.

## Stand 15.11.2026

- **1.4.0 ist veröffentlicht** (Tag `v1.4.0`, Release mit ZIP). PR #1–#3 sind kommentiert, #2 und #3 geschlossen.
- **Auf `staging`, noch nicht veröffentlicht (→ 1.4.1):** Handy-Navigation, Löschschutz auf Touch-Geräten, Cache-Header für `index.html`, größere Kamerakacheln, Doorbell Gen 2 in der README, überarbeitete Dokumentation inkl. Architektur-Schaubild.
- **1.4.1 ist veröffentlicht.**
- **Auf `staging`:** Langsam aufwachende Akku-Kameras werden jetzt von der Webapp geweckt, bevor go2rtc gefragt wird (`RtspHold`). Mit „Mama“ funktioniert der Stream jetzt (3,7 s Aufwachzeit). Den langsamen Fall habe ich in einer isolierten Docker-Umgebung nachgestellt: eine Ersatz-Kamera, die wie ring-mqtt per `exec` erst nach 25 s Bild liefert, mit echtem go2rtc und der neuen Webapp. Ergebnisse:
  - alter Weg: Fehler nach 10 s, wie bei „Mama“ vorher
  - neuer Weg: Bild nach 28,6 s
  - Verlassen beim Aufwachen: bricht sauber ab, go2rtc wird nicht gefragt
  - zwei Zuschauer: beide bekommen Bild, die Kamera läuft, bis der letzte geht
  - Limit überschritten: klare Fehlermeldung statt Hängen
  - Recorder: Clip statt Abbruch nach 15 s
  - Browser per WebRTC: Bild nach etwa 30 s
- **Umgesetzt:** Der Player zeigt beim Aufwachen einen Hinweis („Waking up the camera…“ nach 3 s, „The camera did not respond“ mit „Try again“ nach 75 s). Getestet mit der 25-s-Test-Kamera (WebRTC, MJPEG, Fehlerfall, erneuter Versuch) und mit „Oma“ in Handy-Breite.
- **Offen:** Phasen 2–4.

## Phase 1: Absichern und releasen (kurzfristig, erledigt mit 1.4.0)

1. Fixes reviewen, auf `staging` committen, Images bauen.
2. **Manueller Test auf echter Hardware**, weil das nicht automatisierbar ist:
   - Mit App-Passwort: Live-Stream (WebRTC und MJPEG) und Event-Feed funktionieren nach dem Login, ohne Login nicht.
   - Klingeln: genau **ein** Clip pro Ereignis.
   - `docker compose restart mosquitto` und dann die Webapp neu starten, während der Broker noch fehlt: die Events müssen trotzdem ankommen.
3. Version auf **1.4.0** setzen, `staging` → `main`, Release.

## Phase 2: Offene Produktentscheidungen

- **Ausgeblendete Kameras:** „Ausblenden“ entfernt eine Kamera nur aus dem Dashboard. Für sie werden weiterhin Clips aufgenommen, Events erzeugt und Push-Nachrichten verschickt. Ist das so gewollt? Wenn nicht, muss der Recorder `disabled_cameras` aus `settings.json` beachten und `on_message` müsste diese Kameras ignorieren.
- **Ohne Passwort ist alles offen:** Wer im LAN zuerst `/api/app/set-password` aufruft, setzt das Passwort. Vorschlag: Im Wizard muss ein Passwort gesetzt werden (mit bewusstem Opt-out).

## Phase 3: Qualität und UX (Quick Wins)

- Push-Texte nennen die Device-ID statt des Kameranamens (`send_notification`, `send_device_alert`). Stattdessen `camera_names` verwenden.
- Sessions liegen nur im Speicher, deshalb meldet jedes Update alle Nutzer ab. Persistieren (gehasht) in `data/webapp/`.
- Die Retention-Bereinigung läuft erst eine Stunde nach dem Start. Einmal direkt beim Start ausführen.
- Die Abhängigkeit `docker` ist seit dem Entfernen des Sockets fast tot. Optional machen oder entfernen.
- `starlette.testclient`-Deprecation: `httpx2` in `requirements-dev.txt` aufnehmen.

## Phase 4: Wartbarkeit (mittelfristig)

- `main.py` in Module aufteilen: `settings`, `auth`, `mqtt`, `go2rtc`, `recordings`, `routes/*`. RTSP-URL- und Settings-Logik mit dem Recorder in ein gemeinsames Paket legen, denn die ist heute doppelt vorhanden.
- In der CI das Frontend mitprüfen: `tsc`, `vite build`, ESLint, später Vitest für Hooks (`useEvents`, `useVideoRtc`).
- Image-Tags pinnen (`tsightler/ring-mqtt`, `alexxit/go2rtc`, `eclipse-mosquitto:2`), Renovate/Dependabot einrichten.
- Mosquitto mit Passwort ausliefern (Defense in Depth, auch wenn der Port nicht publiziert ist).
- CSRF: Heute schützt nur `SameSite=Lax`. Zusätzlich die `Origin` bei zustandsändernden Requests prüfen.

## Nachtrag 15.11.2026: Docker-Test, PRs, Upgrade-Pfad

**Beim Docker-Test zusätzlich behoben:** Der Preflight blockierte Neuinstallationen. ring-mqtt nahm das Token aus dem Wizard nie auf. WebRTC verband sich in Docker nie (Ersatzmodus führte zum Decoder-Fehler). Der Ring-Livestream lief nach „Stop“ weiter, wegen eines Lecks im Proxy und im MJPEG-Ersatz.

**PR #2 (faststart):** korrekt und mit einem Test-Clip nachgewiesen, auf `staging` übertragen (der PR zielt auf das alte `main`) und mit Test abgesichert. Nach dem Merge den PR mit Dank schließen.

**PR #3 (1:1-Seitenverhältnis):** so nicht mergen. Das Video Doorbell 3, das einzige getestete Gerät, liefert 16:9. Mit dem PR würde es in ein quadratisches Feld gezwungen. Besser: Das Seitenverhältnis kommt aus den echten Abmessungen (Snapshot bzw. `videoWidth/videoHeight`), Standard 16:9, und das responsive Raster aus dem PR wird übernommen. Außerdem entfernt der PR das Zeilenende am Dateiende in drei Dateien.

**Upgrade 1.3.0 → staging** (in Docker durchgespielt, mit den veröffentlichten 1.3.0-Images und typischen Nutzerdaten):
- Ohne Probleme: Einstellungen, Passwort, Kameranamen/ausgeblendete Kameras, `go2rtc.yaml`, Aufnahmen, Setup-Status. Es ist keine Migration nötig, es gibt nur neue Felder und Dateien.
- Erwartet, aber im CHANGELOG zu erwähnen: Alle Nutzer werden einmal abgemeldet (Sessions liegen im Speicher). Die Ports 1883/1984/8554/55123 sind zu, wer Home Assistant, Frigate o. Ä. direkt auf Mosquitto oder RTSP 8554 zeigen lässt, muss die Ports selbst wieder freigeben.
- **Problem:** `git pull` bricht ab, wenn `docker-compose.yml` lokal geändert wurde, was die README für NAS ausdrücklich empfiehlt. Lösung: lokale Anpassungen in eine `docker-compose.override.yml` (gitignored), README-Abschnitt „Updating“ ergänzen.
- **Doku-Fehler:** Die NAS-Anleitung ändert nur das Recorder-Volume, die Webapp sieht die Aufnahmen dann nicht.
- **Vor dem Release:** Version auf 1.4.0 setzen. Das Image meldet sonst weiter 1.3.0.
- Image-only-Update (nur `docker compose pull`, ohne `git pull`) funktioniert ebenfalls: Die alte Compose-Datei mit Docker-Socket läuft mit den neuen Images. Der Token-Watcher fehlt dann, wird aber nur bei einer Neuinstallation gebraucht.

**PR #1 (Snapshot-404):** korrekt, auf `staging` übernommen. Er wurde am 30.10. ohne Kommentar geschlossen. Nach dem Release dem Autor danken oder ihn wieder öffnen.

**Offen: langsam aufwachende Akku-Kameras.** „Mama“ (Akku 33 %) brauchte 26 s bis zum ersten Bild, go2rtc gibt die RTSP-Verbindung nach 5–10 s auf → kein Stream. „Oma“ (5,5 s) klappt. `#timeout=` an der go2rtc-Quelle half nicht. Zu prüfen: go2rtc-Version bzw. Optionen, ein `ffmpeg:`-Source mit längerem Timeout, oder ein Retry im Player. Das Problem bestand schon vor dieser Session.
