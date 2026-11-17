# Push-Benachrichtigungen

Ring Off kann Hinweise über **ntfy** oder **Gotify** aufs Handy schicken. Füge die URL unter **Settings → Notification URL** ein und wähle, bei welchen Ereignissen du benachrichtigt werden willst.

## ntfy {#ntfy}

[ntfy.sh](https://ntfy.sh) ist kostenlos und braucht für öffentliche Topics kein Konto.

1. Installiere die ntfy-App und abonniere ein Topic mit einem langen, schwer zu erratenden Namen.
2. Füge die Topic-URL in den Einstellungen ein:

```
https://ntfy.sh/dein-geheimes-topic
```

::: warning Topic-Namen sind Passwörter
Wer den Namen eines öffentlichen ntfy-Topics kennt, kann dessen Nachrichten mitlesen. Nimm einen zufälligen Namen oder betreibe einen eigenen ntfy-Server.
:::

## Gotify {#gotify}

[Gotify](https://gotify.net) betreibst du selbst. Lege in Gotify eine Application an, kopiere deren Token und füge die Message-URL ein:

```
https://gotify.deinhost.de/message?token=DEIN_APP_TOKEN
```

## Welche Ereignisse benachrichtigen {#which-events-notify}

| Einstellung | Standard | Wann |
|---|---|---|
| Notify on Doorbell | an | jemand klingelt |
| Notify on Motion | an | Bewegung wird erkannt |
| Notify on Low Battery | an | ein Akku fällt unter **Low Battery Threshold** (standardmäßig 20 %) |
| Notify on Connection Lost | an | ein Gerät geht offline |

## Testen {#test-it}

Im Schritt **Alerts** des Einrichtungsassistenten gibt es den Knopf **Send a test notification**, der den genauen HTTP-Status meldet. Du erreichst ihn über **Settings → Run setup again**.

Die Nachricht wird vom **Server** verschickt, nicht von deinem Browser – der Benachrichtigungsdienst muss also von dem Rechner aus erreichbar sein, auf dem Ring Off läuft.

Es kommt nichts an? Siehe [Push-Benachrichtigungen kommen nicht an](/de/troubleshooting#push-notifications-are-not-delivered).
