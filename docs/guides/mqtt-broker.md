# Existing MQTT broker

If you already run a Mosquitto instance — e.g. as part of Home Assistant — you can point all services at it instead of starting the bundled one.

### 1. Remove the bundled broker

Delete or comment out the entire `mosquitto:` block in `docker-compose.yml` and remove `mosquitto` from every `depends_on`.

::: warning This one change can't go into the override file
An override cannot remove `depends_on` entries, so this edit has to live in `docker-compose.yml`. Update with `git stash && git pull && git stash pop` afterwards — see [Updating](/guide/updating#your-local-changes-would-be-overwritten-by-merge).
:::

### 2. Point ring-mqtt at your broker

ring-mqtt in Docker mode reads its MQTT connection from `data/ring-mqtt/config.json`, not from environment variables. Change `mqtt_url` there and keep the other fields (the Ring token lives in `ring-state.json`, not in this file):

::: code-group

```json [Plain]
{
  "mqtt_url": "mqtt://192.168.1.100:1883"
}
```

```json [With login]
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

### 3. Point the webapp and recorder at your broker

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

### 4. Allow the `ring/#` topic

ring-mqtt publishes and subscribes to the `ring/#` topic tree. Make sure your broker's ACL permits this for your user, or allows anonymous access from the Docker network. Example Mosquitto ACL entry:

```
user myuser
topic readwrite ring/#
```

### 5. Restart

```bash
docker compose up -d
```

Check with `docker compose logs ring-mqtt` that you see `Successfully connected to MQTT broker`.
