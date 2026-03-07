# Jitsi Security and Call Recording Guide

This document covers how to secure your Jitsi deployment with JWT authentication and
configure call recording to a GCP bucket via Jibri.

---

## 1. Jitsi JWT Authentication

JWT authentication prevents unauthorized users from creating or joining Jitsi rooms.
When enabled, the Zulip Calls Plugin generates a short-lived JWT for every call
participant, scoped to the specific room.

### 1.1 Jitsi Server Setup (Prosody)

Install the Prosody JWT module on your Jitsi server:

```bash
apt-get install prosody-modules   # includes mod_auth_token
```

Edit `/etc/prosody/conf.d/your-domain.cfg.lua`:

```lua
VirtualHost "your-domain.example.com"
    authentication = "token"
    app_id = "zulip-calls"
    app_secret = "YOUR_STRONG_SECRET_HERE"
    allow_empty_token = false

    modules_enabled = {
        "presence";
        "ping";
    }

Component "conference.your-domain.example.com" "muc"
    modules_enabled = {
        "muc_meeting_id";
        "token_verification";
    }

Component "internal.auth.your-domain.example.com" "muc"
    storage = "none"
    muc_room_locking = false
    muc_room_default_public_jids = true
```

Restart Prosody:

```bash
systemctl restart prosody
```

### 1.2 Zulip Plugin Configuration

In your Zulip `settings.py` (or via Django settings override):

```python
JITSI_JWT_ENABLED = True
JITSI_JWT_APP_ID = "zulip-calls"          # Must match prosody app_id
JITSI_JWT_SECRET = "YOUR_STRONG_SECRET_HERE"  # Must match prosody app_secret
JITSI_JWT_ALGORITHM = "HS256"
JITSI_JWT_ISSUER = "zulip"
JITSI_JWT_AUDIENCE = "jitsi"
```

Generate a strong secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 1.3 How JWT Tokens Are Generated

For every call, the plugin generates a per-user JWT with these claims:

| Claim | Description |
|-------|-------------|
| `iss` | Issuer (`JITSI_JWT_ISSUER`) |
| `aud` | Audience (`JITSI_JWT_AUDIENCE`) |
| `sub` | Jitsi server domain |
| `room` | The specific Jitsi room name |
| `iat` | Issued-at timestamp |
| `nbf` | Not-before (same as iat) |
| `exp` | Expiry = now + CALL_MAX_DURATION + 5 min buffer |
| `context.user.id` | Zulip user ID |
| `context.user.name` | User display name |
| `context.user.email` | User email |
| `context.user.avatar` | Avatar URL |

The token is appended as `&jwt=<token>` to the Jitsi URL query parameters.

### 1.4 Security Considerations

- Rotate `JITSI_JWT_SECRET` periodically. All active calls will continue to work
  until their tokens expire.
- Keep `CALL_MAX_DURATION` reasonable (default 3600s = 1 hour). The token expires
  5 minutes after max duration to allow for clock skew.
- The secret must be identical on the Zulip server and the Jitsi/Prosody server.
- Use HTTPS for your Jitsi deployment to prevent token interception.

---

## 2. GCP Call Recording via Jibri

Jibri (Jitsi Broadcasting Infrastructure) records Jitsi meetings and can upload
recordings to a GCP Cloud Storage bucket.

### 2.1 Prerequisites

- A Jibri instance running alongside your Jitsi deployment
- A GCP project with Cloud Storage enabled
- A GCP service account with write access to the target bucket

### 2.2 GCP Bucket Setup

```bash
# Create a bucket
gsutil mb -l us-central1 gs://your-org-call-recordings

# Create a service account
gcloud iam service-accounts create jibri-recorder \
    --display-name="Jibri Call Recorder"

# Grant write access to the bucket
gsutil iam ch \
    serviceAccount:jibri-recorder@your-project.iam.gserviceaccount.com:objectCreator \
    gs://your-org-call-recordings

# Create and download the key
gcloud iam service-accounts keys create /tmp/gcp_recording_key.json \
    --iam-account=jibri-recorder@your-project.iam.gserviceaccount.com
```

Copy the key to your Zulip server:

```bash
scp /tmp/gcp_recording_key.json zulip-server:/etc/zulip/gcp_recording_key.json
chmod 640 /etc/zulip/gcp_recording_key.json
chown zulip:zulip /etc/zulip/gcp_recording_key.json
```

### 2.3 Jibri Configuration

Edit `/etc/jitsi/jibri/jibri.conf`:

```hocon
jibri {
    recording {
        recordings-directory = "/tmp/jibri-recordings"
        finalize-script = "/opt/jibri/finalize_recording.sh"
    }
}
```

Create the finalize script at `/opt/jibri/finalize_recording.sh`:

```bash
#!/bin/bash
RECORDING_DIR="$1"
BUCKET="gs://your-org-call-recordings"
KEY_FILE="/etc/jibri/gcp_recording_key.json"

gcloud auth activate-service-account --key-file="$KEY_FILE"

for f in "$RECORDING_DIR"/*.mp4; do
    FILENAME=$(basename "$f")
    TIMESTAMP=$(date -u +"%Y/%m/%d")
    gsutil cp "$f" "$BUCKET/$TIMESTAMP/$FILENAME"
done

rm -rf "$RECORDING_DIR"
```

Make it executable:

```bash
chmod +x /opt/jibri/finalize_recording.sh
```

### 2.4 Zulip Plugin Configuration

```python
CALL_RECORDING_ENABLED = True
CALL_RECORDING_GCP_BUCKET = "your-org-call-recordings"
CALL_RECORDING_GCP_KEY_FILE = "/etc/zulip/gcp_recording_key.json"
CALL_RECORDING_FORMAT = "mp4"
```

### 2.5 Recording Lifecycle

1. When a call starts, Jibri can be triggered to begin recording (via Jitsi's
   recording API or toolbar button).
2. Jibri records the meeting as an MP4 file to its local disk.
3. When the recording ends, the finalize script uploads the file to the GCP bucket
   organized by date (`YYYY/MM/DD/filename.mp4`).
4. Local recordings are cleaned up after upload.

### 2.6 Storage Retention Policy

Configure a lifecycle rule on the GCP bucket to auto-delete old recordings:

```bash
cat > /tmp/lifecycle.json << 'EOF'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 90}
    }
  ]
}
EOF

gsutil lifecycle set /tmp/lifecycle.json gs://your-org-call-recordings
```

This deletes recordings older than 90 days. Adjust as needed for your
compliance requirements.

---

## 3. Jitsi Hardening Checklist

### 3.1 Disable Anonymous Room Creation

With JWT enabled (Section 1), unauthenticated users cannot create rooms.
Ensure `allow_empty_token = false` in Prosody config.

### 3.2 Enable Lobby for Group Calls

In your Jitsi `config.js`:

```javascript
config.enableLobby = true;
config.hideLobbyButton = false;
```

The lobby lets the host approve participants before they join.

### 3.3 Secure Signaling with TLS

Ensure all Jitsi components use TLS:

- Prosody: configure TLS certificates in Prosody config
- Jitsi Videobridge (JVB): use OSSL/SRTP (enabled by default)
- Web interface: HTTPS via nginx/Let's Encrypt

```bash
certbot --nginx -d your-domain.example.com
```

### 3.4 Rate Limiting

Add rate limiting in your nginx config for the Jitsi server:

```nginx
limit_req_zone $binary_remote_addr zone=jitsi:10m rate=10r/s;

server {
    location / {
        limit_req zone=jitsi burst=20 nodelay;
        proxy_pass http://localhost:8080;
    }
}
```

### 3.5 Network Security

- Restrict JVB ports to only the necessary UDP range (10000-20000 by default)
- Use a firewall to block unused ports
- Place Jibri on a private network; it only needs access to Jitsi internally

### 3.6 Disable Unnecessary Features

In Jitsi `config.js`, disable features you don't need:

```javascript
config.disableInviteFunctions = true;
config.enableInsecureRoomNameWarning = false;
config.disableThirdPartyRequests = true;
```
