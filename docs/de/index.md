# Einführung

Ring Off ist ein selbst gehostetes Dashboard für Ring-Türklingeln und -Kameras. Du bekommst Live-Bild, Aufnahmen bei Bewegung und Klingeln auf deiner eigenen Festplatte, Push-Benachrichtigungen sowie Akku- und WLAN-Status – ohne Ring-Protect-Abo.

![Ring-Off-Dashboard](https://m4rcelnoel.github.io/ring-off/webinterface.png)

## Was du bekommst

- **Live-Bild** – WebRTC, MSE oder MJPEG, je nachdem, was Browser und Netz hergeben. Akku-Kameras werden vorher geweckt.
- **Aufnahmen bei Bewegung und Klingeln** – Clips werden lokal gespeichert, Ereignistyp und Dauer sind einstellbar, alte Clips werden automatisch gelöscht.
- **Personenerkennung** – Bewegungen mit erkannter Person bekommen ein eigenes Abzeichen.
- **Push-Benachrichtigungen** – über ntfy.sh oder Gotify, für jeden Ereignistyp einzeln schaltbar.
- **Gerätestatus** – Akkustand und WLAN-Signal der Kameras, WLAN-Signal der Gongs.
- **Einrichtungsassistent** – Ring-Anmeldung mit Zwei-Faktor-Code im Browser, keine Config-Dateien.
- **Automatische Erkennung** – neue Kameras werden von selbst für das Live-Bild eingerichtet.
- **Home-Assistant-Panel**, optionales **Dashboard-Passwort**, **NAS-fähig**, **handytauglich**, Images für **x86-64 und arm64**.

## Aufbau der Dokumentation

| Bereich | Inhalt |
|---|---|
| [Installation](/de/guide/installation) | Voraussetzungen, Schnellstart und Einrichtungsassistent |
| [Aktualisieren](/de/guide/updating) | Neue Versionen holen, Image-Tags, eigene Änderungen behalten |
| [Architektur](/de/guide/architecture) | Welcher Container was macht und wo deine Daten liegen |
| [Umgebungsvariablen](/de/configuration/environment) | Alle Variablen, die Webapp und Recorder lesen |
| [Einstellungen in der Weboberfläche](/de/configuration/settings) | Aufnahme, Benachrichtigungen, Passwort, Kameras |
| [Ports & Sicherheit](/de/configuration/ports) | Freigegebene Ports, Docker-Socket, Broker-Passwort |
| Anleitungen | [Streaming](/de/guides/streaming), [Aufnahmen & NAS](/de/guides/recording), [Benachrichtigungen](/de/guides/notifications), [Home Assistant](/de/guides/home-assistant), [eigener MQTT-Broker](/de/guides/mqtt-broker) |
| [Fehlerbehebung](/de/troubleshooting) | Symptome, Ursachen und Lösungen für die häufigsten Probleme |
| [Entwicklung](/de/development) | Branches, aus dem Quellcode bauen, Tests |

## Getestete Geräte

| Gerät | Status |
|---|---|
| Ring Video Doorbell 3 | ✅ getestet |
| Ring Video Doorbell (2nd Gen) | ✅ läuft laut Nutzer |

Andere Ring-Kameras, die mit [ring-mqtt](https://github.com/tsightler/ring-mqtt) funktionieren, sollten ebenfalls laufen – Akku-Kameras, kabelgebundene Klingeln, Innen- und Außenkameras. Wenn du ein weiteres Modell getestet hast, freue ich mich über einen [Pull Request](https://github.com/m4rcelnoel/ring-off/pulls).

::: info Spricht meine Kamera noch mit Ring?
Ja. Ring-Kameras verbinden sich immer über die Ring-Cloud, das lässt sich nicht umgehen. Ring Off holt Bild und Ereignisse über ring-mqtt ab und speichert Clips, Ereignisse und Einstellungen ausschließlich bei dir.
:::
