# Einstellungen in der Weboberfläche

Öffne **Settings** über das Zahnrad im Dashboard. Die Einstellungen werden in `data/webapp/settings.json` gespeichert und gelten sofort – ein Neustart ist nicht nötig.

::: info Oberfläche auf Englisch
Ring Off selbst ist auf Englisch. Die Namen der Einstellungen stehen hier deshalb so, wie du sie in der App siehst.
:::

## Ring Account {#ring-account}

Zeigt, ob ring-mqtt bei Ring angemeldet ist. **Run setup again** startet den [Einrichtungsassistenten](/de/guide/installation#the-setup-wizard) neu – praktisch, um die Dienste erneut zu prüfen oder dich mit einem anderen Ring-Konto anzumelden.

## Cameras {#cameras}

Kameras umbenennen oder im Dashboard ausblenden. Standardmäßig sind alle sichtbar.

## Video Recording {#recording}

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Record on Motion | an | Clip speichern, wenn Bewegung erkannt wird |
| Record on Doorbell | an | Clip speichern, wenn jemand klingelt |
| Clip Duration (seconds) | 60 | Länge jedes Clips (10–300) |
| Clip Retention (days) | 30 | Ältere Aufnahmen automatisch löschen (0 = für immer behalten) |

Siehe [Aufnahmen & NAS](/de/guides/recording).

## Push Notifications {#notifications}

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Notification URL | – | ntfy.sh-Topic-URL oder Gotify-URL `/message?token=TOKEN` |
| Notify on Motion | an | Push bei Bewegung |
| Notify on Doorbell | an | Push, wenn jemand klingelt |
| Notify on Low Battery | an | Hinweis, wenn ein Akku unter den Schwellwert fällt |
| Low Battery Threshold (%) | 20 | Akkustand, ab dem der Hinweis kommt |
| Notify on Connection Lost | an | Hinweis, wenn ein Gerät offline geht |

Siehe [Push-Benachrichtigungen](/de/guides/notifications).

## Home Assistant {#home-assistant}

| Einstellung | Standard | Bedeutung |
|---|---|---|
| URL | – | Adresse deines Home Assistant, z. B. `http://homeassistant.local:8123` |
| Long-Lived Access Token | – | Token, den du in HA unter Profil → Sicherheit erstellst |
| Entity Filter | `ring, doorbell` | Kommagetrennte Begriffe, die mit Entitäts-IDs und Anzeigenamen abgeglichen werden |

Siehe [Home Assistant](/de/guides/home-assistant).

## App Access {#access}

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Password Protection | aus | Schaltet einen Login vor das Dashboard. Das Passwort wird als bcrypt-Hash gespeichert. |

Um es später zu ändern, brauchst du das **Current Password**.
