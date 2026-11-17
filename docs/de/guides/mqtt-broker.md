# Eigener MQTT-Broker

Wenn du schon eine Mosquitto-Instanz betreibst – etwa als Teil von Home Assistant –, kannst du alle Dienste darauf zeigen lassen, statt den mitgelieferten Broker zu starten.

### 1. Mitgelieferten Broker entfernen {#_1-remove-the-bundled-broker}

Lösche oder kommentiere den ganzen Block `mosquitto:` in `docker-compose.yml` aus und entferne `mosquitto` aus jedem `depends_on`.

::: warning Diese eine Änderung passt nicht in die Override-Datei
Eine Override-Datei kann keine `depends_on`-Einträge entfernen, deshalb muss diese Änderung in `docker-compose.yml` stehen. Aktualisiere danach mit `git stash && git pull && git stash pop` – siehe [Aktualisieren](/de/guide/updating#your-local-changes-would-be-overwritten-by-merge).
:::

### 2. ring-mqtt auf deinen Broker zeigen {#_2-point-ring-mqtt-at-your-broker}

ring-mqtt liest im Docker-Betrieb seine MQTT-Verbindung aus `data/ring-mqtt/config.json`, nicht aus Umgebungsvariablen. Ändere dort `mqtt_url` und lass die anderen Felder stehen (der Ring-Token liegt in `ring-state.json`, nicht in dieser Datei):

::: code-group

```json [Ohne Anmeldung]
{
  "mqtt_url": "mqtt://192.168.1.100:1883"
}
```

```json [Mit Anmeldung]
{
  "mqtt_url": "mqtt://myuser:mypassword@192.168.1.100:1883"
}
```

```json [TLS]
{
  "mqtt_url": "mqtts://192.168.1.100:8883"
}
```

:::

### 3. Webapp und Recorder auf deinen Broker zeigen {#_3-point-the-webapp-and-recorder-at-your-broker}

```yaml
# docker-compose.override.yml
services:
  webapp:
    environment:
      - MQTT_HOST=192.168.1.100
      - MQTT_PORT=1883
  recorder:
    environment:
      - MQTT_HOST=192.168.1.100
      - MQTT_PORT=1883
```

### 4. Das Topic `ring/#` erlauben {#_4-allow-the-ring-topic}

ring-mqtt veröffentlicht und abonniert den Topic-Baum `ring/#`. Sorge dafür, dass die ACL deines Brokers das für deinen Benutzer erlaubt oder anonymen Zugriff aus dem Docker-Netz zulässt. Beispiel für Mosquitto:

```
user myuser
topic readwrite ring/#
```

### 5. Neu starten {#_5-restart}

```bash
docker compose up -d
```

Prüfe mit `docker compose logs ring-mqtt`, ob `Successfully connected to MQTT broker` erscheint.
