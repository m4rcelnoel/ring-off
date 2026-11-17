# Ports & security

## Service ports

Only two ports are published. Everything else talks over the Docker network.

| Service | Port | Published | Purpose |
|---|---|---|---|
| webapp | **8080** | yes | Web UI + API |
| go2rtc | **8555** tcp+udp | yes | WebRTC media — the browser connects here directly for live video |
| go2rtc | 1984 | no | go2rtc UI and API; the webapp proxies what it needs |
| mosquitto | 1883 | no | MQTT broker |
| ring-mqtt | 8554 | no | RTSP streams |
| ring-mqtt | 55123 | no | ring-mqtt's own token setup UI — the setup wizard replaces it |

::: warning 8555 needs both protocols
WebRTC prefers UDP and falls back to TCP. Mapping only one leaves browsers unable to connect on networks that block the other.
:::

Ring Off tells the browser to reach 8555 on the same host name you opened the dashboard with. If you use a reverse proxy on a **different** machine, set [`WEBRTC_CANDIDATE_HOST`](/configuration/environment#commonly-changed) on the webapp to the Docker host's IP.

### Why the others stay closed

The broker allows anonymous connections and ring-mqtt's setup UI has no authentication at all, so publishing them hands anyone on your network your Ring topics and camera streams. Each is a one-line `ports:` entry in `docker-compose.override.yml` if you need it:

```yaml
services:
  mosquitto:
    ports:
      - "1883:1883"   # set a password first, see below
```

## Securing Mosquitto

The default `config/mosquitto.conf` allows anonymous connections on the local Docker network. Before you publish port 1883 — for example for Home Assistant — enable authentication:

```ini
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
```

Create the password file:

```bash
docker exec ring-mosquitto mosquitto_passwd -c /mosquitto/config/passwd myuser
```

Then put the same user and password into ring-mqtt's `mqtt_url` (see [Existing MQTT broker](/guides/mqtt-broker#_2-point-ring-mqtt-at-your-broker)).

## Dashboard password

Switch on **Password Protection** in [Settings](/configuration/settings#access) to put a login screen in front of the dashboard. If you make Ring Off reachable from outside your home network, use it — and put a reverse proxy with HTTPS in front.

## Docker socket

The webapp does **not** mount `/var/run/docker.sock`. That would be root-equivalent access to the host, and this is the container that parses browser input.

It used to be needed to restart go2rtc when a camera appeared and ring-mqtt after a Ring sign-in. Neither is required any more:

- go2rtc is updated over its REST API.
- ring-mqtt is restarted from inside its own container: `config/ring-mqtt-init.sh` watches for the token the wizard writes and restarts ring-mqtt within a few seconds. (ring-mqtt never re-reads its state file on its own once started without a token.)

If you still want the webapp to restart containers itself, mount the socket in `docker-compose.override.yml`:

```yaml
services:
  webapp:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```
