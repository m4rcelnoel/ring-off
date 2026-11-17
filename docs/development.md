# Development

## Branches

Work lands on `staging` first; `main` only ever receives merges from it.

| Branch | CI | Image tag |
|---|---|---|
| `staging` | tests + typecheck, then build | `ghcr.io/…:staging` |
| `main` | tests + typecheck, then build | `ghcr.io/…:main` and `:latest` |
| tag `v*` | — | `:1.4.2`, `:1.4` + GitHub release |

`main` is protected: no direct pushes, and the `Tests` job has to pass before a pull request can be merged. To try a change before it reaches `main`, point the images at `:staging` in `docker-compose.override.yml`:

```yaml
services:
  webapp:   { image: ghcr.io/m4rcelnoel/ring-off-webapp:staging }
  recorder: { image: ghcr.io/m4rcelnoel/ring-off-recorder:staging }
```

## Build from source

`docker-compose.yml` uses pre-built images from GHCR. Use the dev override to build locally instead:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

This builds `webapp` and `recorder` from source and tags them `ring-off-webapp:dev` / `ring-off-recorder:dev`. The other services (`mosquitto`, `ring-mqtt`, `go2rtc`) are unchanged.

## Backend hot-reload

```bash
# Infrastructure only — the dev override publishes its ports on localhost
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d mosquitto ring-mqtt go2rtc

# Backend with hot-reload
cd webapp
pip install -r requirements.txt
./dev.sh
```

`dev.sh` wraps `uvicorn main:app --reload --port 8080`. The defaults compiled into `main.py` are container paths (`/config`, `/videos`) and Docker host names (`mosquitto`, `go2rtc`) that don't resolve on a dev machine, so `dev.sh` points them at the repository's own `config/` and `data/` folders and at the ports `docker-compose.dev.yml` publishes on localhost.

Override any variable by exporting it first, e.g. `PORT=8081 ./dev.sh`. See [Environment variables](/configuration/environment) for the full list.

::: tip ffmpeg
The MJPEG fallback is transcoded with ffmpeg. The Docker image ships it; when running the backend directly, install ffmpeg or `/stream/<name>` returns an empty response.
:::

## Frontend hot-reload

```bash
cd webapp/frontend
npm install
npm run dev   # starts on :5173 with a proxy to :8080
```

## Tests

```bash
pip install -r webapp/requirements.txt -r recorder/requirements.txt -r requirements-dev.txt
pytest
```

The suite runs without Docker, a broker or a Ring account: MQTT topic handling is driven through the real `on_message` callback with a stubbed connection, and every config path is redirected to a temporary directory. CI runs it, together with a frontend typecheck, before any image is built.

## These docs

The documentation is built with [VitePress](https://vitepress.dev) from the Markdown files in `docs/`:

```bash
cd docs
npm install
npm run dev   # http://localhost:5173/ring-off/docs/
```

English pages live in `docs/`, German translations in `docs/de/` with the same file names. Pushing to `main` publishes the site via GitHub Pages.

## Built with

| Project | License | Purpose |
|---|---|---|
| [ring-mqtt](https://github.com/tsightler/ring-mqtt) | MIT | Ring → MQTT bridge + RTSP server |
| [go2rtc](https://github.com/AlexxIT/go2rtc) | MIT | RTSP relay, WebRTC/MSE streaming |
| [Eclipse Mosquitto](https://mosquitto.org) | EPL-2.0 | MQTT broker |
| [FastAPI](https://fastapi.tiangolo.com), [uvicorn](https://www.uvicorn.org) | MIT, BSD | Backend |
| [python-ring-doorbell](https://github.com/python-ring-doorbell/python-ring-doorbell) | LGPL-3.0 | Ring API client & OAuth |
| [paho-mqtt](https://eclipse.dev/paho/), [httpx](https://www.python-httpx.org) | EPL-2.0, BSD | MQTT and HTTP clients |
| [ffmpeg](https://ffmpeg.org) | LGPL/GPL | Transcoding and recording |
| [React](https://react.dev), [Vite](https://vitejs.dev), [Tailwind CSS](https://tailwindcss.com), [Radix UI](https://www.radix-ui.com) | MIT | Frontend |

The full list is in the [README](https://github.com/m4rcelnoel/ring-off#credits--open-source-libraries).
