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

exec /init
