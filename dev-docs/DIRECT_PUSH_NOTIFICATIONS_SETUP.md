# Direct push notifications (bypassing the bouncer)

## Overview

This document explains how to configure a Zulip server to send mobile push notifications **directly to Firebase Cloud Messaging (FCM)** instead of using the Zulip push notification bouncer service.

This is primarily intended for:

- **Custom mobile apps** that use their own Firebase project (not the official Zulip apps), or
- **Development/testing** where you want to validate FCM delivery end‑to‑end.

Using this mode in production with the official Zulip mobile apps is **not supported** and not recommended.

### FCM-Only Support

**Note:** The codebase has been updated to support **FCM-only configurations** in production. Previously, direct push notifications required both FCM (Android) and APNs (iOS) credentials. Now, you can configure FCM-only for Android-only deployments.

**⚠️ TODO: Add APNs Support Later**

Currently, this setup only supports **Android devices via FCM**. To support iOS devices, you will need to:

1. Obtain APNs credentials (certificate or token-based authentication)
2. Configure `APNS_TOKEN_KEY_FILE` or `APNS_CERT_FILE` in your settings
3. Ensure `has_apns_credentials()` returns `True`

See the [iOS push notification setup guide](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#ios) for details on obtaining APNs credentials.

---

## Part 1: Obtain Firebase credentials

### 1.1 Open Firebase Console

1. Go to `https://console.firebase.google.com/`.
2. Sign in with your Google account.
3. Select your existing Firebase project for the mobile app (or create a new one).

The **Firebase project used here must match the project configured in your Android app** (i.e. the `google-services.json` you built the app with).

### 1.2 Enable Cloud Messaging

1. In the Firebase Console, open **Project settings** (gear icon ⚙️ → *Project settings*).
2. Go to the **Cloud Messaging** tab.
3. Ensure that Firebase Cloud Messaging is enabled for the project.
   - If the API is disabled, you may be prompted to enable it in Google Cloud Console.

### 1.3 Create a service account key

1. Still in **Project settings**, open the **Service accounts** tab.
2. Click **Generate new private key**.
3. Confirm the dialog to download a JSON file containing your service account credentials.
4. Store this file securely on your local machine; it grants server‑side access to your Firebase project.

The downloaded JSON should have fields like:

- `type`: `"service_account"`
- `project_id`
- `private_key_id`
- `private_key`
- `client_email`

---

## Part 2: Install credentials on the Zulip server

These steps assume a standard production install where Zulip runs as the `zulip` user.

### 2.1 Copy credentials to the server

Copy the downloaded JSON file to the Zulip server, for example:

```bash
scp path/to/your-firebase-service-account.json zulip-server:/tmp/
```

### 2.2 Move to a secure location

On the Zulip server:

```bash
sudo mkdir -p /etc/zulip
sudo mv /tmp/your-firebase-service-account.json /etc/zulip/firebase-credentials.json
```

### 2.3 Lock down permissions

Make sure only the `zulip` user can read the credentials:

```bash
sudo chown zulip:zulip /etc/zulip/firebase-credentials.json
sudo chmod 600 /etc/zulip/firebase-credentials.json
```

Quick sanity‑check:

```bash
sudo -u zulip head -5 /etc/zulip/firebase-credentials.json
```

You should see the start of a JSON object (do **not** share this content).

---

## Part 3: Production settings changes

All production configuration should go in `/etc/zulip/settings.py`.

### 3.1 Disable the push notification bouncer

Edit `/etc/zulip/settings.py`:

```bash
sudo editor /etc/zulip/settings.py
```

Set `ZULIP_SERVICE_PUSH_NOTIFICATIONS` to `False`:

```python
# Disable the Zulip push notification bouncer; send directly to FCM instead.
ZULIP_SERVICE_PUSH_NOTIFICATIONS = False
```

If the line is commented out like:

```python
# ZULIP_SERVICE_PUSH_NOTIFICATIONS = True
```

uncomment it and change to:

```python
ZULIP_SERVICE_PUSH_NOTIFICATIONS = False
```

This tells Zulip **not** to register with or send through the central bouncer service.

### 3.2 Point Zulip at the Firebase credentials

In the same file, configure the path to your service account JSON:

```python
# Path to the Firebase service account JSON used for FCM.
ANDROID_FCM_CREDENTIALS_PATH = "/etc/zulip/firebase-credentials.json"
```

Use an absolute path. The file must be readable by the `zulip` user.

### 3.3 Restart Zulip

After editing settings, restart the server:

```bash
sudo su zulip -c /home/zulip/deployments/current/scripts/restart-server
```

or on newer systems:

```bash
sudo systemctl restart zulip
```

---

## Part 4: Development server configuration (optional)

For a dev environment (e.g. `localhost:9991` using `./tools/run-dev.py`), you can configure direct FCM in `zproject/dev_settings.py` inside the repo.

Example snippet:

```python
# Disable bouncer for local development and send directly to FCM.
ZULIP_SERVICE_PUSH_NOTIFICATIONS = False

# Local path to your Firebase credentials JSON (on your dev machine).
ANDROID_FCM_CREDENTIALS_PATH = "/absolute/path/to/firebase-credentials.json"
```

After editing, restart the dev server:

```bash
./tools/run-dev.py
```

---

## Part 5: Code Changes for FCM-Only Support

The following code changes enable FCM-only push notifications in production:

### 5.1 Updated Functions

**File:** `zerver/lib/push_notifications.py`

1. **`sends_notifications_directly()`** (line 863-864):
   - Changed from requiring both APNs and FCM credentials (`and`)
   - Now accepts either APNs or FCM credentials (`or`)
   - Allows direct sending with FCM-only configuration

2. **`push_notifications_configured()`** (line 1123-1126):
   - Added new condition to allow FCM-only or APNS-only in production when NOT using bouncer
   - Previously required both credentials in production mode
   - Now supports single-platform deployments

These changes enable the server to recognize FCM-only configurations as valid for direct push notifications, bypassing the previous requirement for both platforms.

---

## Part 6: Verifying the configuration

### 6.1 Check settings from Django shell

On production:

```bash
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from django.conf import settings
print(f'Using bouncer: {settings.ZULIP_SERVICE_PUSH_NOTIFICATIONS}')
print(f'FCM credentials path: {getattr(settings, \"ANDROID_FCM_CREDENTIALS_PATH\", \"Not set\")}')
"
```

Expected output:

```text
Using bouncer: False
FCM credentials path: /etc/zulip/firebase-credentials.json
```

### 6.2 Validate the JSON format

Optional but useful:

```bash
sudo -u zulip python3 -m json.tool /etc/zulip/firebase-credentials.json >/dev/null && \
  echo "Firebase credentials JSON is valid"
```

### 6.3 Monitor FCM logs

Tail logs while sending a test message to a device that has registered an FCM token:

```bash
sudo tail -f /var/log/zulip/django.log | grep -i "FCM"
sudo tail -f /var/log/zulip/errors.log | grep -i "FCM\|firebase"
```

You should see log lines from `zerver.lib.push_notifications` showing FCM messages being constructed and sent.

---

## Part 7: Common issues and troubleshooting

### 7.1 `FCM credentials path: Not set`

- `ANDROID_FCM_CREDENTIALS_PATH` is missing or misspelled in `/etc/zulip/settings.py`.
- The settings file was edited but the server wasn’t restarted.

Fix:

1. Confirm the setting is present and uses an absolute path.
2. Restart Zulip and re‑run the Django shell check.

### 7.2 Permission denied reading credentials

Symptoms in logs: errors mentioning reading `/etc/zulip/firebase-credentials.json`.

Fix:

```bash
sudo chown zulip:zulip /etc/zulip/firebase-credentials.json
sudo chmod 600 /etc/zulip/firebase-credentials.json
```

### 7.3 Firebase authentication / invalid credentials

Possible causes:

- Service account JSON is from the wrong project.
- File is truncated or corrupted.
- Required APIs/permissions are not enabled in Google Cloud.

Checks:

```bash
sudo -u zulip python3 -c "
import json
with open('/etc/zulip/firebase-credentials.json') as f:
    creds = json.load(f)
print('Project ID:', creds.get('project_id'))
print('Client email:', creds.get('client_email'))
"
```

Ensure `project_id` matches the project used by your Android app.

### 7.4 Notifications still not reaching the device

### 7.5 Push notifications not sent for real messages (FCM-only setup)

**Symptom:** Manual FCM test works, but notifications don't trigger for actual messages.

**Cause:** The `push_notifications_configured()` function was returning `False` for FCM-only configurations in production.

**Solution:** Ensure you have the latest code with the FCM-only support changes (see Part 5). The code now allows FCM-only configurations to pass the configuration check.

**Verification:**
```bash
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from zerver.lib.push_notifications import push_notifications_configured, uses_notification_bouncer, has_fcm_credentials
print(f'Push notifications configured: {push_notifications_configured()}')
print(f'Uses bouncer: {uses_notification_bouncer()}')
print(f'Has FCM credentials: {has_fcm_credentials()}')
"
```

Expected output for FCM-only setup:
```
Push notifications configured: True
Uses bouncer: False
Has FCM credentials: True
```

Once FCM is configured and logs show messages being sent, remaining issues are usually on the client side:

- Device token not registered in Zulip.
- Mobile app built with a different Firebase project.
- App missing notification channel / permission configuration.

You can inspect tokens for a given user in a Django shell:

```bash
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from zerver.models import UserProfile, PushDeviceToken
user = UserProfile.objects.get(id=43)  # Replace with your user ID
tokens = PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.FCM)
print(f'Found {tokens.count()} FCM tokens for {user.email}')
for token in tokens:
    print('  Token prefix:', token.token[:32], '...')
"
```

---

## Security considerations

- **Do not** commit the Firebase credentials JSON to Git or any VCS.
- Store the file in a restricted location (`/etc/zulip` with `600` permissions).
- Rotate service account keys periodically in the Firebase/Google Cloud console.
- Use separate Firebase projects/credentials for development vs. production.

---

## Quick checklist

- [ ] Firebase project created and FCM enabled.
- [ ] Service account JSON downloaded from Firebase Console → *Project settings* → *Service accounts*.
- [ ] Credentials file copied to `/etc/zulip/firebase-credentials.json` with secure permissions.
- [ ] `ZULIP_SERVICE_PUSH_NOTIFICATIONS = False` set in `/etc/zulip/settings.py`.
- [ ] `ANDROID_FCM_CREDENTIALS_PATH` set to the correct absolute path.
- [ ] Code updated with FCM-only support (see Part 5).
- [ ] Zulip server restarted.
- [ ] Logs show FCM messages being sent when push notifications are triggered.
- [ ] Custom mobile app receives notifications using tokens from this Firebase project.
- [ ] **TODO:** Add APNs credentials for iOS support (currently FCM-only).

