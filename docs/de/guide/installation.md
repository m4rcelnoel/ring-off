# Installation

## Voraussetzungen

| Voraussetzung | Version |
|---|---|
| Docker | 24+ |
| Docker Compose | v2.20+ (Plugin) |
| Ring-Konto | beliebig – ein Abo ist **nicht** nötig |
| CPU | x86-64 oder arm64 (z. B. Raspberry Pi 4/5) |

Jeder Rechner, der durchläuft, reicht: Heimserver, NAS mit Docker oder Raspberry Pi.

## Schnellstart {#quick-start}

### 1. Repository klonen

```bash
git clone https://github.com/m4rcelnoel/ring-off.git
cd ring-off
```

### 2. Stack starten

```bash
docker compose up -d
```

::: tip Keine Config-Dateien kopieren
`config/go2rtc.yaml` wird beim ersten Start automatisch angelegt, und Kameras werden eingetragen, sobald sie gefunden werden. Es gibt keine `.env` zum Ausfüllen – die RTSP-Zugangsdaten für den internen Stream-Server von ring-mqtt erzeugt ring-mqtt selbst, Ring Off übernimmt sie automatisch.
:::

### 3. Weboberfläche öffnen

Öffne **`http://<deine-server-ip>:8080`** und folge dem Einrichtungsassistenten.

## Der Einrichtungsassistent {#the-setup-wizard}

Die Schritte heißen in der App so (die Oberfläche ist auf Englisch):

1. **Checks** – testet Broker, ring-mqtt, go2rtc und die Datenordner und sagt dir genau, was zu tun ist, falls etwas nicht stimmt.
2. **Ring** – E-Mail und Passwort, dazu ein Zwei-Faktor-Code, falls dein Konto einen nutzt.
3. **Devices** – Kameras und Gongs erscheinen, sobald ring-mqtt sie meldet.
4. **Cameras** – gib jeder einen Namen („Haustür“ statt `Camera 169F41`) und blende aus, was du nicht brauchst.
5. **Alerts** – optional Aufnahmen und Push-Nachrichten, mit einem Testknopf, der meldet, was wirklich passiert ist.
6. **Finish** – optional ein Dashboard-Passwort setzen.

Der Ring-Refresh-Token wird in `data/ring-mqtt/ring-state.json` gespeichert, und ring-mqtt wird innerhalb weniger Sekunden neu gestartet, um ihn zu laden. Du musst dich nur einmal anmelden; der Token übersteht Neustarts.

Danach kannst du unter **Settings → Cameras** jederzeit Kameras umbenennen oder ausblenden. **Run setup again** im selben Bereich startet den ganzen Assistenten neu, z. B. um dich mit einem anderen Ring-Konto anzumelden.

::: details Die eigene Token-Oberfläche von ring-mqtt (Port 55123)
ring-mqtt hat eine eigene Seite zur Token-Einrichtung auf Port 55123. Du brauchst sie nicht, und sie ist nicht freigegeben, weil sie keinerlei Anmeldung hat. Falls die Anmeldung in Ring Off scheitert, kannst du sie vorübergehend in `docker-compose.override.yml` freigeben und danach wieder entfernen:

```yaml
services:
  ring-mqtt:
    ports: ["55123:55123"]
```
:::

## Optionale Dienste {#optional-services}

`go2rtc` (Live-Bild) und `recorder` (Aufnahmen) sind standardmäßig dabei. Um einen davon abzuschalten, ohne `docker-compose.yml` zu bearbeiten, gib ihm in `docker-compose.override.yml` ein inaktives Profil:

```yaml
services:
  recorder:
    profiles: ["disabled"]
```

## Eigene Änderungen gehören in die Override-Datei {#local-changes-belong-in-the-override-file}

Bearbeite nie `docker-compose.yml` selbst – sie wird bei jedem Update ersetzt. NAS-Pfade, zusätzliche Ports und Umgebungsvariablen gehören in `docker-compose.override.yml`. Compose lädt sie automatisch, git ignoriert sie:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

Die Beispieldatei enthält fertige Abschnitte für die häufigsten Fälle, die du nur einkommentieren musst. Warum das wichtig ist, steht unter [Aktualisieren](/de/guide/updating).

## Nächste Schritte {#next-steps}

- Zeitzone setzen, damit Clip-Namen zur Ortszeit passen: [`TZ`](/de/configuration/environment#tz)
- Clips auf dem NAS speichern: [Aufnahmen & NAS](/de/guides/recording#store-recordings-on-a-nas)
- Benachrichtigungen aufs Handy: [Push-Benachrichtigungen](/de/guides/notifications)
