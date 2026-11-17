# Home Assistant

Ring Off kann deine Ring-bezogenen Entitäten aus Home Assistant in einem eigenen **HA**-Bereich anzeigen.

## Home Assistant verbinden {#connect-home-assistant}

1. Öffne in Home Assistant dein **Profil → Sicherheit** und erstelle einen **langlebigen Zugriffstoken** (Long-Lived Access Token).
2. Öffne in Ring Off die **Settings** und trage unter **Home Assistant → URL** deine HA-Adresse ein, z. B. `http://homeassistant.local:8123`.
3. Füge den Token unter **Long-Lived Access Token** ein und speichere.

Der Bereich **HA** in der Seitenleiste (am Handy in der unteren Leiste) zeigt dann die passenden Entitäten.

## Entitätsfilter {#entity-filter}

Standardmäßig zeigt der Bereich Entitäten, deren ID oder Anzeigename `ring` oder `doorbell` enthält. Heißen deine anders – etwa auf Deutsch –, passe **Entity Filter** in den Einstellungen an. Er nimmt kommagetrennte Begriffe:

```
ring, doorbell, klingel, haustür
```

## Den MQTT-Broker teilen {#sharing-the-mqtt-broker}

Home Assistant kann die Geräte von ring-mqtt auch direkt über MQTT lesen. Dafür gibt es zwei Wege:

- **Den Broker von Home Assistant für alles nutzen** – siehe [Eigener MQTT-Broker](/de/guides/mqtt-broker).
- **Den mitgelieferten Broker für Home Assistant freigeben** – erst ein Passwort setzen, dann Port 1883 freigeben. Siehe [Mosquitto absichern](/de/configuration/ports#securing-mosquitto).
