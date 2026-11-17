# Recording & NAS

The **recorder** service listens for motion and doorbell events on MQTT and saves a clip with ffmpeg for each one. The webapp lists, plays and deletes them in the **Recordings** panel (bottom bar on phones).

## What gets recorded

Configure it in [Settings → Video Recording](/configuration/settings#recording):

- **Record on Motion** and **Record on Doorbell** — switch each event type on or off
- **Clip Duration** — 10 to 300 seconds, 60 by default
- **Clip Retention** — clips older than this many days are deleted automatically (0 keeps them forever)

A few rules worth knowing:

- One recording per camera runs at a time. An event that arrives while a clip is still recording is skipped.
- A failed attempt is retried three times; the log shows ffmpeg's last error line.
- The recorder stops recording when less than **512 MB** is free on the recordings volume, and logs how much is left.

## Where clips are stored

By default in `data/videos/`, one folder per camera:

```
data/videos/
└── <device_id>/
    ├── 20260316_124334_motion.mp4
    └── 20260316_134512_ding.mp4
```

Filenames use the container's local time — set [`TZ`](/configuration/environment#tz) so they match yours.

## Store recordings on a NAS

Point **both** the recorder and the webapp at your NAS mount. The recorder writes the clips, the webapp lists, plays and deletes them. If only the recorder moves, clips are saved but the Recordings panel stays empty.

Put this in `docker-compose.override.yml`, not in `docker-compose.yml`, so updates keep working:

```yaml
services:
  recorder:
    volumes:
      - /mnt/nas/ring-videos:/videos   # ← your NAS mount point
  webapp:
    volumes:
      - /mnt/nas/ring-videos:/videos   # ← the same folder
```

```bash
docker compose up -d
```

Compose replaces the default `./data/videos:/videos` mount with this one, because both target `/videos`.

::: tip Keep existing clips
Clips are not moved automatically. Copy `data/videos/*` to the NAS folder if you want to keep them.
:::

The NAS share must be mounted on the Docker host (e.g. via `/etc/fstab`) before the containers start, and the containers must be able to write to it.

## Turning recording off

To run Ring Off without recording at all, disable the recorder service in `docker-compose.override.yml`:

```yaml
services:
  recorder:
    profiles: ["disabled"]
```

Recordings missing? See [Recordings are not being saved](/troubleshooting#recordings-are-not-being-saved).
