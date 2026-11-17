# Entwicklung

## Branches {#branches}

Änderungen landen zuerst auf `staging`; `main` bekommt nur Merges von dort.

| Branch | CI | Image-Tag |
|---|---|---|
| `staging` | Tests + Typecheck, dann Build | `ghcr.io/…:staging` |
| `main` | Tests + Typecheck, dann Build | `ghcr.io/…:main` und `:latest` |
| Tag `v*` | – | `:1.4.2`, `:1.4` + GitHub-Release |

`main` ist geschützt: keine direkten Pushes, und der Job `Tests` muss grün sein, bevor ein Pull Request gemergt werden kann. Um eine Änderung vor `main` auszuprobieren, zeig die Images in `docker-compose.override.yml` auf `:staging`:

```yaml
services:
  webapp:   { image: ghcr.io/m4rcelnoel/ring-off-webapp:staging }
  recorder: { image: ghcr.io/m4rcelnoel/ring-off-recorder:staging }
```

## Aus dem Quellcode bauen {#build-from-source}

`docker-compose.yml` nutzt fertige Images aus der GHCR. Mit dem Dev-Override baust du stattdessen lokal:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Das baut `webapp` und `recorder` aus dem Quellcode und taggt sie als `ring-off-webapp:dev` / `ring-off-recorder:dev`. Die übrigen Dienste (`mosquitto`, `ring-mqtt`, `go2rtc`) bleiben unverändert.

## Backend mit Hot-Reload {#backend-hot-reload}

```bash
# Nur die Infrastruktur – der Dev-Override gibt ihre Ports auf localhost frei
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d mosquitto ring-mqtt go2rtc

# Backend mit Hot-Reload
cd webapp
pip install -r requirements.txt
./dev.sh
```

`dev.sh` ist ein Wrapper um `uvicorn main:app --reload --port 8080`. Die in `main.py` eingebauten Standardwerte sind Container-Pfade (`/config`, `/videos`) und Docker-Hostnamen (`mosquitto`, `go2rtc`), die auf einem Entwicklungsrechner nicht auflösen. `dev.sh` biegt sie auf die Ordner `config/` und `data/` im Repository und auf die Ports um, die `docker-compose.dev.yml` auf localhost freigibt.

Jede Variable lässt sich vorher exportieren, z. B. `PORT=8081 ./dev.sh`. Die vollständige Liste steht unter [Umgebungsvariablen](/de/configuration/environment).

::: tip ffmpeg
Der MJPEG-Fallback wird mit ffmpeg umgewandelt. Das Docker-Image bringt es mit; startest du das Backend direkt, installiere ffmpeg, sonst liefert `/stream/<name>` eine leere Antwort.
:::

## Frontend mit Hot-Reload {#frontend-hot-reload}

```bash
cd webapp/frontend
npm install
npm run dev   # läuft auf :5173 mit Proxy auf :8080
```

## Tests {#tests}

```bash
pip install -r webapp/requirements.txt -r recorder/requirements.txt -r requirements-dev.txt
pytest
```

Die Tests laufen ohne Docker, Broker oder Ring-Konto: Die MQTT-Verarbeitung wird über den echten `on_message`-Callback mit einer simulierten Verbindung getestet, und jeder Config-Pfad zeigt auf ein temporäres Verzeichnis. Die CI führt sie zusammen mit einem Typecheck des Frontends aus, bevor ein Image gebaut wird.

## Diese Dokumentation {#these-docs}

Die Dokumentation wird mit [VitePress](https://vitepress.dev) aus den Markdown-Dateien in `docs/` gebaut:

```bash
cd docs
npm install
npm run dev   # http://localhost:5173/ring-off/docs/
```

Englische Seiten liegen in `docs/`, deutsche Übersetzungen in `docs/de/` mit denselben Dateinamen. Ein Push auf `main` veröffentlicht die Seite über GitHub Pages.

## Gebaut mit {#built-with}

| Projekt | Lizenz | Zweck |
|---|---|---|
| [ring-mqtt](https://github.com/tsightler/ring-mqtt) | MIT | Ring → MQTT-Brücke + RTSP-Server |
| [go2rtc](https://github.com/AlexxIT/go2rtc) | MIT | RTSP-Relay, WebRTC/MSE-Streaming |
| [Eclipse Mosquitto](https://mosquitto.org) | EPL-2.0 | MQTT-Broker |
| [FastAPI](https://fastapi.tiangolo.com), [uvicorn](https://www.uvicorn.org) | MIT, BSD | Backend |
| [python-ring-doorbell](https://github.com/python-ring-doorbell/python-ring-doorbell) | LGPL-3.0 | Ring-API-Client & OAuth |
| [paho-mqtt](https://eclipse.dev/paho/), [httpx](https://www.python-httpx.org) | EPL-2.0, BSD | MQTT- und HTTP-Clients |
| [ffmpeg](https://ffmpeg.org) | LGPL/GPL | Umwandlung und Aufnahme |
| [React](https://react.dev), [Vite](https://vitejs.dev), [Tailwind CSS](https://tailwindcss.com), [Radix UI](https://www.radix-ui.com) | MIT | Frontend |

Die vollständige Liste steht im [README](https://github.com/m4rcelnoel/ring-off#credits--open-source-libraries).
