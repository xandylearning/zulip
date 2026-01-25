# Push Notification Data-Only Mode

## Summary

Zulip can send FCM push notifications in two ways:

| Mode | Setting | FCM payload | Best for |
|------|---------|-------------|----------|
| **Data + notification** (default) | `FCM_DATA_ONLY_PUSH = False` | `data` + `notification` | System shows a notification when the app is terminated (killed). |
| **Data-only** | `FCM_DATA_ONLY_PUSH = True` | `data` only | Apps that render their own rich notifications and want to avoid duplicates. |

## Why Data-Only?

When the app always builds and shows notifications from the `data` payload (e.g. with a `DisplayManager` or `firebase_messaging`’s `onMessage` + local notifications), sending both `notification` and `data` causes:

1. **Duplicate notifications** – The system shows one from the `notification` block, and the app shows another from `data`.
2. **Limited look and behavior** – The system notification is generic (no avatars, custom actions, or grouping).

**Advantages of data-only:**

- **Full customization** – You control title, body, icons, avatars, and actions.
- **No duplicates** – Only one notification, the one your app shows.
- **Rich content** – Avatars, message-style layout, action buttons.
- **Grouping** – E.g. bundle several messages from the same stream/topic.
- **Deep linking** – Navigate to the right stream/topic/call when the user taps.

**Limitation:**

- When the app is **terminated**, the system may not show anything. The app only sees the message when it is started or woken by a high-priority data message (platform-dependent). If you need a visible notification while the app is fully killed, use the default **data + notification** mode (see [FCM_TERMINATED_APP_FIX.md](FCM_TERMINATED_APP_FIX.md)).

## Your Situation: Duplicates

If you see two notifications (one generic, one from your app), the backend is using **data + notification**. Your app is correctly handling `data` and showing a rich notification, but the system is also showing the one from the `notification` block.

**Fix:** Use data-only so only your app displays notifications.

## Enabling Data-Only

In your Django settings (e.g. `zproject/settings.py` or `zproject/dev_settings.py`):

```python
FCM_DATA_ONLY_PUSH = True
```

This is respected for:

- E2EE and legacy message push notifications (`send_android_push_notification`),
- Call-related FCM sends (`create_fcm_call_notification_message` / `send_fcm_call_notifications`).

No `notification` or `android.notification` block is sent; only the `data` payload is used. Your app must:

1. Subscribe to FCM `data` messages (e.g. `onMessage` and/or background handler).
2. Parse the `data` map and show a local notification with your desired UI.
3. Handle tap to open the correct screen (stream, topic, call, etc.).

## Implementation Details

- **Setting:** `FCM_DATA_ONLY_PUSH` in `zproject/default_settings.py` (default `False`).
- **General FCM path:** `zerver/lib/push_notifications.py` → `send_android_push_notification()`. When data-only is on, `_create_fcm_notification_content()` is skipped and no `notification` / `android.notification` is added.
- **Call path:** `create_fcm_call_notification_message()` builds a message with only `data` and `android=AndroidConfig(priority="high")` when `FCM_DATA_ONLY_PUSH` is True.

## Related

- [FCM_TERMINATED_APP_FIX.md](FCM_TERMINATED_APP_FIX.md) – Why and how Zulip uses data + notification by default.
- [PUSH_NOTIFICATION_DIAGNOSTICS.md](PUSH_NOTIFICATION_DIAGNOSTICS.md) – Debugging delivery and processing.
