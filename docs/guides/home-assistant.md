# Home Assistant

Ring Off can show your Ring-related Home Assistant entities in its own **HA** panel.

## Connect Home Assistant

1. In Home Assistant, open your **Profile → Security** and create a **Long-Lived Access Token**.
2. In Ring Off, open **Settings** and enter your HA address under **Home Assistant → URL**, e.g. `http://homeassistant.local:8123`.
3. Paste the token into **Long-Lived Access Token** and save.

The **HA** panel in the sidebar (bottom bar on phones) then lists matching entities.

## Entity filter

By default the panel shows entities whose ID or friendly name contains `ring` or `doorbell`. If yours are named differently — for example in another language — adjust **Entity Filter** in Settings. It takes comma-separated terms:

```
ring, doorbell, klingel, haustür
```

## Sharing the MQTT broker

Home Assistant can also read ring-mqtt's devices directly over MQTT. You have two options:

- **Use Home Assistant's broker for everything** — see [Existing MQTT broker](/guides/mqtt-broker).
- **Publish Ring Off's bundled broker** to Home Assistant — add a password first, then publish port 1883. See [Securing Mosquitto](/configuration/ports#securing-mosquitto).
