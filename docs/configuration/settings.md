# Settings in the web UI

Open **Settings** with the gear icon in the dashboard. Settings are stored in `data/webapp/settings.json` and take effect immediately — no restart needed.

## Ring Account

Shows whether ring-mqtt is signed in to Ring. **Run setup again** replays the [setup wizard](/guide/installation#the-setup-wizard) — useful to re-check the services or sign in to a different Ring account.

## Cameras

Rename cameras or hide them from the dashboard. All cameras are shown by default.

## Video Recording {#recording}

| Setting | Default | Description |
|---|---|---|
| Record on Motion | on | Save a clip when motion is detected |
| Record on Doorbell | on | Save a clip when the doorbell is pressed |
| Clip Duration (seconds) | 60 | Length of each clip (10–300) |
| Clip Retention (days) | 30 | Auto-delete recordings older than this (0 = keep forever) |

See [Recording & NAS](/guides/recording).

## Push Notifications {#notifications}

| Setting | Default | Description |
|---|---|---|
| Notification URL | — | ntfy.sh topic URL or Gotify `/message?token=TOKEN` URL |
| Notify on Motion | on | Push on motion events |
| Notify on Doorbell | on | Push when the doorbell rings |
| Notify on Low Battery | on | Alert when a battery drops below the threshold |
| Low Battery Threshold (%) | 20 | Battery level that triggers the alert |
| Notify on Connection Lost | on | Alert when a device goes offline |

See [Push notifications](/guides/notifications).

## Home Assistant

| Setting | Default | Description |
|---|---|---|
| URL | — | Your Home Assistant address, e.g. `http://homeassistant.local:8123` |
| Long-Lived Access Token | — | Token created in HA under Profile → Security |
| Entity Filter | `ring, doorbell` | Comma-separated terms matched against entity IDs and friendly names |

See [Home Assistant](/guides/home-assistant).

## App Access {#access}

| Setting | Default | Description |
|---|---|---|
| Password Protection | off | Puts a login screen in front of the dashboard. The password is stored as a bcrypt hash. |

To change it later you need the **Current Password**.
