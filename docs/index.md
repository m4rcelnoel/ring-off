# Introduction

Ring Off is a self-hosted dashboard for Ring doorbells and cameras. It gives you live streams, motion and doorbell recordings stored on your own disk, push notifications and battery/WiFi status — without a Ring Protect subscription.

![Ring Off dashboard](https://m4rcelnoel.github.io/ring-off/webinterface.png)

## What you get

- **Live streams** — WebRTC, MSE or MJPEG, whichever your browser and network allow. Battery cameras are woken up first.
- **Recording on motion and doorbell presses** — clips saved locally, configurable per event type and duration, with automatic retention.
- **Person detection** — motion events with an identified person get their own badge.
- **Push notifications** — via ntfy.sh or Gotify, switchable per event type.
- **Device status** — battery level and WiFi signal for cameras, WiFi signal for chimes.
- **Setup wizard** — Ring sign-in with 2FA in the browser, no config files to edit.
- **Auto-discovery** — new cameras are added to the stream relay automatically.
- **Home Assistant panel**, optional **dashboard password**, **NAS-ready**, **phone-friendly**, images for **x86-64 and arm64**.

## How the docs are organised

| Section | What's in it |
|---|---|
| [Installation](/guide/installation) | Requirements, quick start and the setup wizard |
| [Updating](/guide/updating) | Pulling new versions, image tags, keeping local changes |
| [Architecture](/guide/architecture) | Which container does what, and where your data lives |
| [Environment variables](/configuration/environment) | Every variable the webapp and recorder read |
| [Settings in the web UI](/configuration/settings) | Recording, notifications, password, cameras |
| [Ports & security](/configuration/ports) | Published ports, the Docker socket, broker authentication |
| Guides | [Streaming](/guides/streaming), [recording & NAS](/guides/recording), [notifications](/guides/notifications), [Home Assistant](/guides/home-assistant), [existing MQTT broker](/guides/mqtt-broker) |
| [Troubleshooting](/troubleshooting) | Symptoms, causes and fixes for the common problems |
| [Development](/development) | Branches, building from source, tests |

## Tested hardware

| Device | Status |
|---|---|
| Ring Video Doorbell 3 | ✅ Tested |
| Ring Video Doorbell (2nd Gen) | ✅ Reported working |

Other Ring cameras that work with [ring-mqtt](https://github.com/tsightler/ring-mqtt) should work too — battery cameras, wired doorbells, indoor and outdoor cameras. If you've tested another model, please [open a pull request](https://github.com/m4rcelnoel/ring-off/pulls).

::: info Does my camera still talk to Ring?
Yes. Ring cameras always connect through the Ring cloud; there is no way around that. Ring Off fetches video and events through ring-mqtt and stores clips, events and settings only on your machine.
:::
