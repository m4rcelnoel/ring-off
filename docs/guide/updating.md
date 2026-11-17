# Updating

```bash
cd ring-off
git pull
docker compose pull
docker compose up -d
```

`git pull` updates the compose file and `config/ring-mqtt-init.sh`; `docker compose pull` fetches the new images. Your data in `data/`, `config/go2rtc.yaml` and the settings made in the web UI are kept — no migration step is needed.

::: warning Before a minor-version update
Read the **Upgrading** notes in the [changelog](https://github.com/m4rcelnoel/ring-off/blob/main/CHANGELOG.md) before going from e.g. 1.3 to 1.4.
:::

## "Your local changes would be overwritten by merge"

If you edited `docker-compose.yml` (a NAS path, an extra port, an environment variable), `git pull` stops with this message. Move those changes into `docker-compose.override.yml` — Compose loads it automatically and git ignores it:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml   # then edit
git checkout -- docker-compose.yml                                   # drop your edits to the original
git pull
```

If you'd rather keep your edited file, this re-applies your changes on top of the update:

```bash
git stash && git pull && git stash pop
```

## Installed from a release ZIP

Extract the new ZIP into a separate folder and copy over only `docker-compose.yml` and the files in `config/` that it contains — never `data/` or your own `config/go2rtc.yaml`. Keep your own changes in `docker-compose.override.yml` there as well, so the copied `docker-compose.yml` doesn't undo them.

## Docker images and tags

Pre-built multi-platform images (amd64 + arm64) are published to GitHub Container Registry:

| Image | Tags |
|---|---|
| `ghcr.io/m4rcelnoel/ring-off-webapp` | `latest`, `1.4`, `1.4.2`, `staging` |
| `ghcr.io/m4rcelnoel/ring-off-recorder` | `latest`, `1.4`, `1.4.2`, `staging` |

- `latest` follows `main`
- version tags (`1.4.2`, `1.4`) are fixed releases
- `staging` is the pre-release branch

`docker-compose.yml` pulls `latest`. To pin a version, set `image:` for both services in `docker-compose.override.yml`:

```yaml
services:
  webapp:   { image: ghcr.io/m4rcelnoel/ring-off-webapp:1.4.2 }
  recorder: { image: ghcr.io/m4rcelnoel/ring-off-recorder:1.4.2 }
```

To build the images yourself, see [Development](/development#build-from-source).
