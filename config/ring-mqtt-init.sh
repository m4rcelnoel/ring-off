#!/bin/sh
# Patch ring-mqtt config.json with required defaults if any fields are missing.
# This is needed because ring-mqtt's first-run token setup (port 55123) writes
# a minimal config containing only ring_token, omitting mqtt_url and other fields
# which causes "Invalid URL" errors and MQTT broker connection failures.

CONFIG=/data/config.json

if [ -f "$CONFIG" ] && ! grep -q '"mqtt_url"' "$CONFIG"; then
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
