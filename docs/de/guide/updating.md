# Aktualisieren

```bash
cd ring-off
git pull
docker compose pull
docker compose up -d
```

`git pull` aktualisiert die Compose-Datei und `config/ring-mqtt-init.sh`, `docker compose pull` holt die neuen Images. Deine Daten in `data/`, `config/go2rtc.yaml` und die Einstellungen aus der Weboberfläche bleiben erhalten – ein Migrationsschritt ist nicht nötig.

::: warning Vor einem Minor-Update
Lies vor einem Sprung von z. B. 1.3 auf 1.4 die Hinweise unter **Upgrading** im [Changelog](https://github.com/m4rcelnoel/ring-off/blob/main/CHANGELOG.md).
:::

## „Your local changes would be overwritten by merge“ {#your-local-changes-would-be-overwritten-by-merge}

Wenn du `docker-compose.yml` bearbeitet hast (NAS-Pfad, zusätzlicher Port, Umgebungsvariable), bricht `git pull` mit dieser Meldung ab. Verschiebe deine Änderungen nach `docker-compose.override.yml` – Compose lädt sie automatisch, git ignoriert sie:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml   # dann anpassen
git checkout -- docker-compose.yml                                   # eigene Änderungen am Original verwerfen
git pull
```

Willst du deine bearbeitete Datei lieber behalten, spielt das hier deine Änderungen nach dem Update wieder ein:

```bash
git stash && git pull && git stash pop
```

## Aus einem Release-ZIP installiert {#installed-from-a-release-zip}

Entpacke das neue ZIP in einen eigenen Ordner und kopiere nur `docker-compose.yml` und die darin enthaltenen Dateien aus `config/` hinüber – nie `data/` oder deine eigene `config/go2rtc.yaml`. Halte auch dort eigene Änderungen in `docker-compose.override.yml`, damit die kopierte `docker-compose.yml` sie nicht überschreibt.

## Docker-Images und Tags {#docker-images-and-tags}

Fertige Images für amd64 und arm64 liegen in der GitHub Container Registry:

| Image | Tags |
|---|---|
| `ghcr.io/m4rcelnoel/ring-off-webapp` | `latest`, `1.4`, `1.4.2`, `staging` |
| `ghcr.io/m4rcelnoel/ring-off-recorder` | `latest`, `1.4`, `1.4.2`, `staging` |

- `latest` folgt `main`
- Versions-Tags (`1.4.2`, `1.4`) sind feste Releases
- `staging` ist der Vorabversions-Branch

`docker-compose.yml` zieht `latest`. Um eine Version festzuhalten, setze `image:` für beide Dienste in `docker-compose.override.yml`:

```yaml
services:
  webapp:   { image: ghcr.io/m4rcelnoel/ring-off-webapp:1.4.2 }
  recorder: { image: ghcr.io/m4rcelnoel/ring-off-recorder:1.4.2 }
```

Wie du die Images selbst baust, steht unter [Entwicklung](/de/development#build-from-source).
