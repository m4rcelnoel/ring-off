# Aufnahmen & NAS

Der Dienst **recorder** hört über MQTT auf Bewegung und Klingeln und speichert für jedes Ereignis einen Clip mit ffmpeg. Die Webapp listet, spielt und löscht sie im Bereich **Recordings** (am Handy in der unteren Leiste).

## Was aufgenommen wird {#what-gets-recorded}

Einstellbar unter [Settings → Video Recording](/de/configuration/settings#recording):

- **Record on Motion** und **Record on Doorbell** – jeden Ereignistyp einzeln an- oder abschalten
- **Clip Duration** – 10 bis 300 Sekunden, standardmäßig 60
- **Clip Retention** – Clips, die älter als so viele Tage sind, werden automatisch gelöscht (0 behält sie für immer)

Gut zu wissen:

- Pro Kamera läuft immer nur eine Aufnahme. Ein Ereignis, das während einer laufenden Aufnahme kommt, wird übersprungen.
- Ein fehlgeschlagener Versuch wird dreimal wiederholt; das Log zeigt die letzte Fehlerzeile von ffmpeg.
- Der Recorder hört auf aufzunehmen, wenn auf dem Aufnahme-Volume weniger als **512 MB** frei sind, und schreibt ins Log, wie viel noch übrig ist.

## Wo die Clips liegen {#where-clips-are-stored}

Standardmäßig in `data/videos/`, ein Ordner pro Kamera:

```
data/videos/
└── <device_id>/
    ├── 20260316_124334_motion.mp4
    └── 20260316_134512_ding.mp4
```

Die Dateinamen nutzen die Ortszeit des Containers – setze [`TZ`](/de/configuration/environment#tz), damit sie zu deiner passen.

## Aufnahmen auf dem NAS speichern {#store-recordings-on-a-nas}

Richte **beide** – Recorder und Webapp – auf deine NAS-Freigabe. Der Recorder schreibt die Clips, die Webapp listet, spielt und löscht sie. Ziehst du nur den Recorder um, werden Clips gespeichert, aber der Bereich Recordings bleibt leer.

Trag das in `docker-compose.override.yml` ein, nicht in `docker-compose.yml`, damit Updates weiter funktionieren:

```yaml
services:
  recorder:
    volumes:
      - /mnt/nas/ring-videos:/videos   # ← dein NAS-Mountpunkt
  webapp:
    volumes:
      - /mnt/nas/ring-videos:/videos   # ← derselbe Ordner
```

```bash
docker compose up -d
```

Compose ersetzt damit das Standard-Mount `./data/videos:/videos`, weil beide auf `/videos` zeigen.

::: tip Vorhandene Clips behalten
Clips werden nicht automatisch verschoben. Kopiere `data/videos/*` in den NAS-Ordner, wenn du sie behalten willst.
:::

Die NAS-Freigabe muss auf dem Docker-Host eingehängt sein (z. B. über `/etc/fstab`), bevor die Container starten, und die Container müssen darauf schreiben dürfen.

## Aufnahmen abschalten {#turning-recording-off}

Um Ring Off ganz ohne Aufnahmen zu betreiben, deaktiviere den Recorder in `docker-compose.override.yml`:

```yaml
services:
  recorder:
    profiles: ["disabled"]
```

Aufnahmen fehlen? Siehe [Aufnahmen werden nicht gespeichert](/de/troubleshooting#recordings-are-not-being-saved).
