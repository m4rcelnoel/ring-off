# Troubleshooting

## Quick health check

```bash
docker compose ps                        # all containers should be "Up"
docker compose logs --tail=50 <service>  # check a specific service
```

The setup wizard's **Checks** step runs the same health checks from the browser: **Settings → Run setup again**.

## Cameras do not appear in the dashboard

1. **Make sure you've signed in to Ring** — at `http://<host>:8080`. See [ring-mqtt is waiting for a Ring token](#ring-mqtt-is-waiting-for-a-ring-token).
2. **Check ring-mqtt is connected to the broker** — see [ring-mqtt cannot connect to the MQTT broker](#ring-mqtt-cannot-connect-to-the-mqtt-broker).
3. **Check ring-mqtt is authenticated with Ring:**
   ```bash
   docker compose logs ring-mqtt | grep -E "Ring API|token"
   ```
   You should see `Successfully established connection to Ring API`. If not, the refresh token has expired — sign in again in the web UI.
4. **Check MQTT topics are being published:**
   ```bash
   docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v -W 10
   ```
   You should see `ring/<location>/camera/<device_id>/...` topics within a few seconds.
5. **Check go2rtc knows your cameras:**
   ```bash
   docker exec ring-webapp python -c "import httpx; print(httpx.get('http://go2rtc:1984/api/streams').text)"
   ```
   Each camera should be listed. go2rtc's own UI on port 1984 isn't published; add it in `docker-compose.override.yml` if you want to open it.

## No live stream / black screen

1. **Check go2rtc can pull the RTSP feed from ring-mqtt:**
   ```bash
   docker compose logs go2rtc | grep -i "error\|rtsp"
   ```
2. **Check the stream URLs in `config/go2rtc.yaml`.** They must match `livestream_user` / `livestream_pass` in `data/ring-mqtt/config.json` (no credentials at all if those keys are absent). Ring Off rewrites them automatically on start and whenever the dashboard loads. Literal `${RTSP_USER}` placeholders mean you're on a version older than 1.3.0.
3. **Check the device IDs.** Run the MQTT subscriber above and compare the IDs with `config/go2rtc.yaml`.
4. **Check the stream host.** Entries must name a host go2rtc itself can resolve — normally `ring-mqtt`. `localhost` there means the file was written by a backend running outside Docker; set `GO2RTC_RTSP_HOST=ring-mqtt` (the default) and restart the webapp, which repairs existing entries.
5. **Check go2rtc kept its WebRTC listener.** `docker compose logs go2rtc` should show **both**:
   ```
   [webrtc] listen tcp addr=[::]:8555
   [webrtc] listen udp addr=...:8555
   ```
   If the TCP line is missing, something else in `config/go2rtc.yaml` took port 8555 — usually a leftover `rtsp: listen: ':8555'` from a pre-1.3.0 config. Remove it.
6. **Check port 8555 is reachable from the browser** — TCP and UDP, at the host name you opened the dashboard with. Behind a reverse proxy on another machine, set [`WEBRTC_CANDIDATE_HOST`](/configuration/environment#commonly-changed).
7. **Try the MJPEG button** on the camera card. If MJPEG works but WebRTC doesn't, the problem is WebRTC negotiation — usually step 6.
8. **Battery cameras that wake slowly** can take 20 s or more for the first frame. The webapp log shows `Camera <id> awake after …s`. If a camera regularly needs longer, raise [`STREAM_WAKE_TIMEOUT`](/guides/streaming#battery-cameras) for the webapp and the recorder.

::: details Upgrading from 1.2.5 or older
The `${RTSP_USER}` placeholders came from `.env`, and your Ring account email/password were never the right credentials — an unescaped `@` also made the URL unparseable. Ring Off now repairs existing entries on start, and `.env` is no longer used.
:::

## No motion or ding events

1. **Check the recorder is connected to MQTT:**
   ```bash
   docker compose logs recorder | grep -i "mqtt\|error"
   ```
2. **Check events are published on MQTT:**
   ```bash
   docker exec ring-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'ring/#' -v
   # then trigger motion or press the doorbell
   ```
3. **Check the webapp WebSocket** — in the browser dev tools' Network tab, the `/ws/events` WebSocket should show `OPEN`.

## Recordings are not being saved

1. **Check the recorder logs:** `docker compose logs recorder`
2. **Check the recording settings** — *Record on Motion* and *Record on Doorbell*. The log says `motion recording disabled, skipping` when one is off.
3. **Check disk space** — the recorder stops below 512 MB free on the recordings volume and logs how much is left.
4. **Check the volume is writable** — the recorder must be able to write to `/videos`. On a NAS, both the recorder and the webapp need the mount — see [Recording & NAS](/guides/recording#store-recordings-on-a-nas).
5. **A clip was skipped** — one recording per camera runs at a time; an event during a running clip is skipped. Failed attempts are retried three times and logged with ffmpeg's last error line.

## Push notifications are not delivered

1. **Check the server can reach the service** — the request comes from the server, not your browser:
   ```bash
   docker exec ring-webapp python -c "import httpx; print(httpx.post('https://ntfy.sh/your-topic', content=b'test').status_code)"
   ```
   `200` means the server can reach ntfy.sh. The wizard's **Alerts** step has a test button that reports the exact HTTP status.
2. **Check the webapp logs** for HTTP errors when events fire:
   ```bash
   docker compose logs webapp | grep -i "notif\|error"
   ```

## ring-mqtt is waiting for a Ring token

**Symptom:** `No refresh token was found in the state file, use the Web UI at http://<host_ip_address>:55123/ to generate a token` in the ring-mqtt logs. No cameras appear.

**Cause:** ring-mqtt has never been authenticated. This is expected on a fresh install.

**Fix:** Sign in through the Ring Off web UI on port 8080. It performs the OAuth exchange (including 2FA), writes the refresh token to `data/ring-mqtt/ring-state.json`, and `config/ring-mqtt-init.sh` restarts ring-mqtt within a few seconds so it loads the token. You only need to do this once.

::: info `ring-state.json`, not `config.json`
ring-mqtt reads the token from the state file; `config.json` has no `ring_token` field. Before 1.3.0 the web UI wrote it to the wrong file, so signing in appeared to succeed while ring-mqtt stayed unauthenticated.
:::

## ring-mqtt cannot connect to the MQTT broker

**Symptom:** Repeated `Unable to connect to MQTT broker` lines in `docker compose logs ring-mqtt`.

**Cause:** Usually a fresh install where ring-mqtt's first-run token setup wrote a minimal `config.json` without `mqtt_url`. Since 1.2.1, `config/ring-mqtt-init.sh` adds the missing fields on every start, so a restart repairs it:

```bash
docker compose restart ring-mqtt
```

If it persists, check that `mqtt_url` in `data/ring-mqtt/config.json` points at your broker (`mqtt://mosquitto:1883` for the bundled one). After the restart you should see `Successfully connected to MQTT broker`.

## ring-mqtt shows `Invalid URL` on startup

**Symptom:** `WARNING - Unhandled Promise Rejection / Invalid URL` in the ring-mqtt logs.

**Cause and fix:** Same as above — `mqtt_url` is missing or empty in `data/ring-mqtt/config.json`. Restart ring-mqtt.

## ring-mqtt restarts in a loop

**Symptom:** `No configuration file found at /data/config.json` followed by `A critical error was detected, shutting down container...`, repeating forever. `docker compose ps` shows ring-mqtt as `Restarting`.

**Cause:** ring-mqtt refuses to start without a config file, and on a fresh install the `data/ring-mqtt/` volume is empty.

**Fix:** Update to 1.3.0 or later, where `config/ring-mqtt-init.sh` writes a complete default config before ring-mqtt starts. On older versions, create `data/ring-mqtt/config.json` by hand and restart:

```json
{ "mqtt_url": "mqtt://mosquitto:1883", "ring_topic": "ring", "enable_cameras": true }
```

## Mosquitto fails to write its log file

**Symptom:** `Error: Unable to open log file /mosquitto/log/mosquitto.log for writing` on startup.

**Cause:** The log directory is owned by root on the host, but the `mosquitto` user (UID 1883) in the container can't write to it.

**Fix A (recommended):** Remove the `log_dest file` line from `config/mosquitto.conf`. Docker already captures stdout.

**Fix B:** Fix the permissions:

```bash
sudo chown -R 1883:1883 data/mosquitto-log
docker compose restart mosquitto
```

## Battery and WiFi not showing on camera cards

**Cause (before 1.2.2):** The device ID was taken from go2rtc's active producers, which only exist while someone is streaming.

**Fix:** Update to 1.2.2 or later.

## Still stuck?

[Open an issue](https://github.com/m4rcelnoel/ring-off/issues) with your Ring Off version, the camera model and the relevant lines from `docker compose logs`.
