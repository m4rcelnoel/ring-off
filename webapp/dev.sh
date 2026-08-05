#!/bin/sh
# Run the backend directly on the host for development.
#
# The defaults in main.py are container paths (/config, /videos) and Docker
# network hostnames (mosquitto, go2rtc), none of which exist on a dev machine.
# This points them at the repository's own config/ and data/ directories, and at
# the ports the compose stack publishes on localhost.
#
#   docker compose up -d mosquitto ring-mqtt go2rtc   # infrastructure
#   ./dev.sh                                          # backend on :8080
#   cd frontend && npm run dev                        # frontend on :5173
#
# Override any of these by exporting them before running.
set -e
cd "$(dirname "$0")"

export GO2RTC_CONFIG="${GO2RTC_CONFIG:-../config/go2rtc.yaml}"
export RING_MQTT_CONFIG="${RING_MQTT_CONFIG:-../data/ring-mqtt/config.json}"
export SETTINGS_FILE="${SETTINGS_FILE:-../data/webapp/settings.json}"
export VIDEO_PATH="${VIDEO_PATH:-../data/videos}"
export MQTT_HOST="${MQTT_HOST:-localhost}"
export GO2RTC_URL="${GO2RTC_URL:-http://localhost:1984}"
export GO2RTC_WS_URL="${GO2RTC_WS_URL:-ws://localhost:1984}"
export RTSP_HOST="${RTSP_HOST:-localhost}"

mkdir -p ../data/webapp ../data/videos ../data/ring-mqtt

exec uvicorn main:app --reload --port "${PORT:-8080}"
