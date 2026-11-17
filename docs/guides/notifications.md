# Push notifications

Ring Off can push alerts to your phone through **ntfy** or **Gotify**. Paste the endpoint URL into **Settings → Notification URL** and choose which events should notify you.

## ntfy

[ntfy.sh](https://ntfy.sh) is free and needs no account for public topics.

1. Install the ntfy app on your phone and subscribe to a topic with a long, hard-to-guess name.
2. Paste the topic URL into Settings:

```
https://ntfy.sh/your-secret-topic
```

::: warning Topic names are passwords
Anyone who knows a public ntfy topic name can read its messages. Use a random name, or run your own ntfy server.
:::

## Gotify

[Gotify](https://gotify.net) is self-hosted. Create an application in Gotify, copy its token and paste the message URL:

```
https://gotify.yourhost.com/message?token=YOUR_APP_TOKEN
```

## Which events notify

| Setting | Default | Sent when |
|---|---|---|
| Notify on Doorbell | on | the doorbell is pressed |
| Notify on Motion | on | motion is detected |
| Notify on Low Battery | on | a battery drops below the **Low Battery Threshold** (20 % by default) |
| Notify on Connection Lost | on | a device goes offline |

## Test it

The setup wizard's **Alerts** step has a **Send a test notification** button that reports the exact HTTP status. Open it via **Settings → Run setup again**.

The request is sent from the **server**, not your browser — the notification service must be reachable from the machine running Ring Off.

Nothing arriving? See [Push notifications are not delivered](/troubleshooting#push-notifications-are-not-delivered).
