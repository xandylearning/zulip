# Google Cloud Storage for uploads

This guide explains how to store Zulip's uploaded media (message
attachments, images, video, audio, voice messages, documents) — plus
avatars, emoji, icons, logos, and exports — in **Google Cloud Storage
(GCS)**.

Zulip has no native GCS backend. Instead, it reuses its existing
**S3 backend** (`zerver/lib/upload/s3.py`, built on `boto3`) pointed at
GCS's **S3-compatible (XML) API** endpoint
(`https://storage.googleapis.com`). Resumable/chunked uploads are
handled by the bundled **tusd** server, which talks to GCS **natively**.

This is a supported configuration: the base
[upload backends guide](upload-backends.md#google-cloud-platform) documents
the core recipe. This page expands it into a complete, security-focused
walkthrough specific to this fork.

```{contents} On this page
:local:
:depth: 2
```

## How it works

Two server components write to and read from the **same** GCS uploads
bucket, but they authenticate **differently**:

| Component | Responsibility | Auth mechanism | Where configured |
| --- | --- | --- | --- |
| **Django / boto3** (`zerver/lib/upload/s3.py`) | Regular upload, download, delete, listing, presigned URLs | **HMAC keys** (GCS "interoperability" keys) | `s3_key` / `s3_secret_key` in `/etc/zulip/zulip-secrets.conf` |
| **tusd** (`zerver/management/commands/runtusd.py`) | Resumable / chunked uploads from clients | **Service-account JSON** | `/etc/zulip/gcp_key.json` |

```{important}
The **bucket is the same**, but the **credentials are not**. You must
provide *both* an HMAC key (for Django) *and* a service-account JSON
(for tusd). If you supply only one, uploads will partially fail —
typically small uploads succeed via boto3 while large resumable uploads
fail via tusd, or vice versa.

For least privilege, generate the HMAC key **for** the same service
account whose JSON key you give to tusd, so a single GCP identity backs
both paths.
```

When tusd is configured for GCS, the startup command automatically
selects native GCS mode:

```python
# zerver/management/commands/runtusd.py
elif settings.S3_ENDPOINT_URL in (
    "https://storage.googleapis.com",
    "https://storage.googleapis.com/",
):
    tusd_args.append(f"-gcs-bucket={settings.S3_AUTH_UPLOADS_BUCKET}")
    env_vars["GCS_SERVICE_ACCOUNT_FILE"] = "/etc/zulip/gcp_key.json"
```

So the service-account file path (`/etc/zulip/gcp_key.json`) is **fixed**
— place the JSON key there exactly.

## Security model

```{warning}
Understanding which bucket is private and which is public is the most
important part of this setup. Getting it wrong exposes user media.
```

Zulip uses **two** buckets with **opposite** access policies:

### Uploads bucket — `S3_AUTH_UPLOADS_BUCKET` → must be **private**

This holds all message media (your primary concern). It must **never**
be world-readable. Security is enforced by Zulip itself, not by the
bucket being open:

1. Every download hits Django's `serve_file()`
   (`zerver/views/upload.py`), which calls `validate_attachment_request()`
   (`zerver/lib/attachments.py`). That function checks file ownership,
   realm-public status, channel subscription, and direct-message
   recipiency. Unauthorized requests get **403**.
2. Only after passing authorization does Zulip mint a **short-lived
   presigned URL** (valid for **60 seconds** —
   `SIGNED_UPLOAD_URL_DURATION` in `s3.py`).
3. In production, nginx fetches the object from GCS internally via
   `X-Accel-Redirect`; the signed URL is never exposed to the browser,
   and responses are marked `Cache-Control: private`.

If you make this bucket public, you bypass `validate_attachment_request`
entirely — anyone who obtains or guesses an object path can read any
file. **Enable "Public access prevention" on this bucket.**

### Avatar bucket — `S3_AVATAR_BUCKET` → intended to be **public-read**

This holds avatars, custom emoji, realm icons/logos, and (by default)
exports. Zulip generates **plain, unsigned public URLs** for these
(`construct_public_upload_url_base()` in `s3.py`), because a single
`GET /messages` response can require hundreds of avatar URLs and signing
each would be too slow. This bucket is **meant** to be world-readable.

```{note}
Even if you only care about message media, you must still configure
`S3_AVATAR_BUCKET`. The S3 backend constructor reads both bucket
settings at startup. Keep the uploads bucket private and the avatar
bucket public-read.
```

### Exports

By default, exports are written into the **public** avatar bucket so
their download links are easy to generate. If you don't want exports
publicly fetchable, set `S3_EXPORT_BUCKET` to a **third, private**
bucket; export links are then 1-week presigned URLs. See
[Data export bucket](upload-backends.md#data-export-bucket).

## Provisioning GCS

You can use the Cloud Console UI or the `gcloud` / `gsutil` CLI. The CLI
commands below assume you've run `gcloud auth login` and
`gcloud config set project YOUR_PROJECT_ID`.

```{tip}
Run interactive login yourself in this session by typing, e.g.,
`! gcloud auth login` so its output lands in the conversation.
```

Pick names and a region/location up front:

```bash
PROJECT_ID="your-project-id"
LOCATION="US"                       # or a region, e.g. us-east1
UPLOADS_BUCKET="yourorg-zulip-uploads"
AVATAR_BUCKET="yourorg-zulip-avatars"
SA_NAME="zulip-storage"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
```

### 1. Create the buckets

```bash
# Private uploads bucket — uniform access + public access prevention
gcloud storage buckets create "gs://${UPLOADS_BUCKET}" \
  --location="${LOCATION}" \
  --uniform-bucket-level-access \
  --public-access-prevention

# Public-read avatar bucket — uniform access, NO public access prevention
gcloud storage buckets create "gs://${AVATAR_BUCKET}" \
  --location="${LOCATION}" \
  --uniform-bucket-level-access \
  --no-public-access-prevention
```

### 2. Create the service account and grant bucket access

```bash
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="Zulip storage"

# Object Admin on BOTH buckets (read + write + delete + list)
gcloud storage buckets add-iam-policy-binding "gs://${UPLOADS_BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

gcloud storage buckets add-iam-policy-binding "gs://${AVATAR_BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"
```

### 3. Make the avatar bucket world-readable

```bash
gcloud storage buckets add-iam-policy-binding "gs://${AVATAR_BUCKET}" \
  --member="allUsers" \
  --role="roles/storage.objectViewer"
```

```{warning}
Do **not** add `allUsers` to the uploads bucket. It must stay private.
```

### 4. Create the service-account JSON key (for tusd)

```bash
gcloud iam service-accounts keys create gcp_key.json \
  --iam-account="${SA_EMAIL}"
```

Copy `gcp_key.json` to the Zulip server at exactly `/etc/zulip/gcp_key.json`
and secure it:

```bash
sudo install -o zulip -g zulip -m 600 gcp_key.json /etc/zulip/gcp_key.json
```

### 5. Create the HMAC key (for Django / boto3)

HMAC keys cannot be created with plain `gcloud`; use `gsutil` (bound to
the **same** service account) or the Console
(**Cloud Storage → Settings → Interoperability → Create a key for a
service account**):

```bash
gsutil hmac create "${SA_EMAIL}"
```

This prints an **Access ID** (starts with `GOOG...`) and a **Secret**.
Save both — the secret is shown only once.

## Configuring Zulip

### `/etc/zulip/settings.py`

```python
# Comment OUT local uploads — this is what activates the GCS/S3 backend.
# LOCAL_UPLOADS_DIR = "/home/zulip/uploads"

S3_AUTH_UPLOADS_BUCKET = "yourorg-zulip-uploads"   # PRIVATE bucket (message media)
S3_AVATAR_BUCKET       = "yourorg-zulip-avatars"   # PUBLIC-read bucket (required)
S3_ENDPOINT_URL        = "https://storage.googleapis.com"
S3_SKIP_CHECKSUM       = True     # required for GCS; avoids XAmzContentSHA256Mismatch

# Optional: a separate PRIVATE bucket for exports (otherwise they go in
# the public avatar bucket). See upload-backends.md#data-export-bucket.
# S3_EXPORT_BUCKET = "yourorg-zulip-exports"

# Optional: set only if you hit region/addressing errors.
# S3_REGION = "us-east1"
```

```{note}
Leave `S3_ADDRESSING_STYLE` at its default (`"auto"`). The documented
GCS recipe does not require path-style addressing; only change it if you
actually encounter addressing errors.
```

### `/etc/zulip/zulip-secrets.conf`

Add the HMAC key under the `[secrets]` section:

```ini
[secrets]
s3_key = GOOG1EXAMPLEACCESSID
s3_secret_key = your-hmac-secret-value
```

These map to `S3_KEY` / `S3_SECRET_KEY` (see `zproject/computed_settings.py`).

### `/etc/zulip/gcp_key.json`

Already placed in step 4 — the service-account JSON used by tusd.

### Restart

```bash
/home/zulip/deployments/current/scripts/restart-server
```

## Configuration summary

| Item | Value / location | Used by |
| --- | --- | --- |
| `S3_AUTH_UPLOADS_BUCKET` | private GCS bucket | Django + tusd |
| `S3_AVATAR_BUCKET` | public-read GCS bucket | Django |
| `S3_ENDPOINT_URL` | `https://storage.googleapis.com` | Django + tusd selector |
| `S3_SKIP_CHECKSUM` | `True` | Django + tusd |
| `s3_key` / `s3_secret_key` (secrets) | GCS HMAC key | Django (boto3) |
| `/etc/zulip/gcp_key.json` | service-account JSON | tusd |

## Migrating existing local uploads

If you already have files stored locally, transfer them **before**
removing `LOCAL_UPLOADS_DIR`:

1. Configure all GCS settings and secrets above, but **leave**
   `LOCAL_UPLOADS_DIR` set — the migration tool reads it to find your
   files.
2. Run the transfer:
   ```bash
   ./manage.py transfer_uploads_to_s3
   ```
3. Comment out `LOCAL_UPLOADS_DIR` and restart the server.

See
[Migrating from local uploads](upload-backends.md#migrating-from-local-uploads-to-amazon-s3-backend)
for details and caveats (e.g. org avatar/logo are not migrated by the tool).

## Verifying the setup

After restarting:

1. **Small upload (boto3 path):** drag a small image into a message. It
   should send, render a thumbnail, and download correctly.
2. **Large upload (tusd path):** upload a file larger than a few MB to
   exercise resumable upload through tusd.
3. **Avatar:** change your profile picture; confirm it loads (served as
   a public URL from the avatar bucket).
4. **Authorization:** confirm a logged-out user cannot fetch a private
   attachment URL directly (should be redirected to login / 403).
5. **Bucket contents:** objects should appear under
   `gs://yourorg-zulip-uploads/<realm_id>/...`.

Check `/var/log/zulip/errors.log` and the tusd logs if anything fails.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `XAmzContentSHA256Mismatch` exceptions | Checksums sent to GCS | Set `S3_SKIP_CHECKSUM = True` (flows into both boto3 and tusd) |
| Small uploads work, large ones fail | tusd missing/invalid `gcp_key.json` | Verify `/etc/zulip/gcp_key.json` exists, is valid, and the SA has Object Admin on the uploads bucket |
| Large uploads work, small ones fail | Bad/missing HMAC key | Verify `s3_key` / `s3_secret_key` in `zulip-secrets.conf` |
| Avatars/emoji return 403 | Avatar bucket not public | Grant `allUsers` `roles/storage.objectViewer` on `S3_AVATAR_BUCKET` |
| Any attachment publicly reachable | Uploads bucket is public | Enable public-access-prevention; remove any `allUsers` binding |
| Addressing / region errors | Endpoint/region mismatch | Confirm `S3_ENDPOINT_URL`; optionally set `S3_REGION`; try `S3_ADDRESSING_STYLE = "path"` only if needed |

## Related documentation

- [File upload backends](upload-backends.md) — base S3/GCS backend reference
- [Security model](security-model.md) — uploaded-file security model
- [Data export and import](export-and-import.md) — export bucket behavior
