#!/bin/sh
# Ensure /data/config.json exists and contains every field ring-mqtt requires.
#
# Two separate problems are handled here:
#
#  1. ring-mqtt (Docker mode) refuses to start at all when config.json is
#     missing — "No configuration file found at /data/config.json", followed by
#     an immediate shutdown. On a fresh deployment the data volume is empty, so
#     the container crash-loops and the token setup UI on :55123 never comes up,
#     leaving no way to create the file it is demanding.
#
#  2. That token setup UI writes a minimal config containing only ring_token,
#     omitting mqtt_url and friends, which then causes "Invalid URL" errors and
#     MQTT broker connection failures.
#
# Creating a complete config without a token is safe: ring-mqtt starts, reports
# that no refresh token was found, and serves the setup UI on :55123.

CONFIG=/data/config.json

if [ ! -f "$CONFIG" ]; then
  mkdir -p /data
  cat > "$CONFIG" <<'EOF'
{
  "mqtt_url": "mqtt://mosquitto:1883",
  "mqtt_options": "",
  "livestream_user": "",
  "livestream_pass": "",
  "disarm_code": "",
  "enable_cameras": true,
  "enable_modes": false,
  "enable_panic": false,
  "hass_topic": "homeassistant/status",
  "ring_topic": "ring",
  "location_ids": []
}
EOF
  echo "ring-mqtt-init: created default config.json (no Ring token yet)"
elif ! grep -q '"mqtt_url"' "$CONFIG"; then
  node -e "
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('$CONFIG', 'utf8'));
const defaults = {
  mqtt_url: 'mqtt://mosquitto:1883',
  mqtt_options: '',
  enable_cameras: true,
  enable_modes: false,
  enable_panic: false,
  hass_topic: 'homeassistant/status',
  ring_topic: 'ring',
  location_ids: [],
  disarm_code: ''
};
// defaults first so existing values win on merge
const merged = Object.assign(defaults, data);
fs.writeFileSync('$CONFIG', JSON.stringify(merged, null, 2));
console.log('ring-mqtt-init: patched config.json with missing MQTT defaults');
"
fi

# ── Pick up a token written by the Ring Off setup wizard ─────────────────────
# When ring-mqtt starts without a token it serves its web UI and then waits
# only for a token submitted through that UI. It never re-reads ring-state.json
# (lib/main.js → handleNoToken), and its 60-second retry applies only to a token
# that already existed and failed. The wizard writes the token straight into
# the state file, so without a restart a fresh install waited forever on
# "Waiting for the first device…".
#
# This watcher bridges that gap without the Docker socket: once a token appears
# it stops the node process, and s6 (which supervises ring-mqtt) restarts it
# with the token loaded. It handles only the no-token → token transition and
# then exits — ring-mqtt rewrites the token itself on every refresh, so
# watching for changes beyond that would restart it in a loop.
STATE=/data/ring-state.json

has_token() {
  [ -f "$STATE" ] && node -e "
    const s = JSON.parse(require('fs').readFileSync('$STATE', 'utf8'));
    process.exit(s.ring_token ? 0 : 1);
  " 2>/dev/null
}

if ! has_token; then
  (
    until has_token; do sleep 3; done
    echo "ring-mqtt-init: Ring token found — restarting ring-mqtt to load it"
    pkill -f 'node .*ring-mqtt.js'
  ) &
fi

exec /init
