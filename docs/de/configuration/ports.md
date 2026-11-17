# Ports & Sicherheit

## Ports der Dienste {#service-ports}

Nur zwei Ports sind freigegeben. Alles andere läuft über das Docker-Netzwerk.

| Dienst | Port | Freigegeben | Zweck |
|---|---|---|---|
| webapp | **8080** | ja | Weboberfläche + API |
| go2rtc | **8555** tcp+udp | ja | WebRTC-Video – der Browser verbindet sich hier direkt für das Live-Bild |
| go2rtc | 1984 | nein | Oberfläche und API von go2rtc; die Webapp leitet weiter, was sie braucht |
| mosquitto | 1883 | nein | MQTT-Broker |
| ring-mqtt | 8554 | nein | RTSP-Streams |
| ring-mqtt | 55123 | nein | Eigene Token-Oberfläche von ring-mqtt – der Einrichtungsassistent ersetzt sie |

::: warning 8555 braucht beide Protokolle
WebRTC bevorzugt UDP und weicht auf TCP aus. Wer nur eines freigibt, sperrt Browser in Netzen aus, die das andere blockieren.
:::

Ring Off sagt dem Browser, dass er Port 8555 unter demselben Hostnamen erreicht, mit dem du das Dashboard geöffnet hast. Nutzt du einen Reverse Proxy auf einem **anderen** Rechner, setze [`WEBRTC_CANDIDATE_HOST`](/de/configuration/environment#commonly-changed) bei der Webapp auf die IP des Docker-Hosts.

### Warum die anderen geschlossen bleiben {#why-the-others-stay-closed}

Der Broker erlaubt anonyme Verbindungen, und die Token-Oberfläche von ring-mqtt hat gar keine Anmeldung. Wer sie freigibt, gibt jedem in deinem Netz deine Ring-Topics und Kamerabilder. Jeder Port ist eine Zeile `ports:` in `docker-compose.override.yml`, falls du ihn brauchst:

```yaml
services:
  mosquitto:
    ports:
      - "1883:1883"   # vorher ein Passwort setzen, siehe unten
```

## Mosquitto absichern {#securing-mosquitto}

Die mitgelieferte `config/mosquitto.conf` erlaubt anonyme Verbindungen im lokalen Docker-Netz. Bevor du Port 1883 freigibst – etwa für Home Assistant –, schalte die Anmeldung ein:

```ini
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
```

Passwortdatei anlegen:

```bash
docker exec ring-mosquitto mosquitto_passwd -c /mosquitto/config/passwd myuser
```

Trage danach denselben Benutzer und dasselbe Passwort in die `mqtt_url` von ring-mqtt ein (siehe [Eigener MQTT-Broker](/de/guides/mqtt-broker#_2-point-ring-mqtt-at-your-broker)).

## Dashboard-Passwort {#dashboard-password}

Schalte **Password Protection** in den [Einstellungen](/de/configuration/settings#access) ein, um einen Login vor das Dashboard zu schalten. Wenn Ring Off von außerhalb deines Heimnetzes erreichbar ist, solltest du das tun – und einen Reverse Proxy mit HTTPS davorsetzen.

## Docker-Socket {#docker-socket}

Die Webapp bindet `/var/run/docker.sock` **nicht** ein. Das wäre Zugriff mit Root-Rechten auf den Host – und genau dieser Container verarbeitet Eingaben aus dem Browser.

Früher war er nötig, um go2rtc bei einer neuen Kamera und ring-mqtt nach einer Ring-Anmeldung neu zu starten. Beides braucht es nicht mehr:

- go2rtc wird über seine REST-API aktualisiert.
- ring-mqtt wird aus seinem eigenen Container heraus neu gestartet: `config/ring-mqtt-init.sh` wartet auf den Token, den der Assistent schreibt, und startet ring-mqtt innerhalb weniger Sekunden neu. (Einmal ohne Token gestartet, liest ring-mqtt seine Zustandsdatei nie von selbst neu ein.)

Willst du trotzdem, dass die Webapp Container selbst neu startet, binde den Socket in `docker-compose.override.yml` ein:

```yaml
services:
  webapp:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```
