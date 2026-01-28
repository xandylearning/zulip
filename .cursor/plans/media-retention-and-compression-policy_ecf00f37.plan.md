---
name: media-retention-and-compression-policy
overview: Implement a media retention policy where attachments are auto-deleted after ~60 days while keeping message records, and introduce image recompression on upload.
todos:
  - id: update-data-models
    content: Add media_expires_at and deleted_from_storage fields to Attachment and ArchivedAttachment models in zerver/models/messages.py.
    status: pending
  - id: implement-upload-expiration-logic
    content: Update upload logic in zerver/lib/upload/__init__.py to set media_expires_at on new uploads based on retention policy.
    status: pending
  - id: implement-cleanup-job
    content: Create a storage cleanup job in zerver/lib/retention.py to physically delete expired media files and thumbnails.
    status: pending
  - id: update-serving-logic
    content: Modify zerver/views/upload.py to handle expired media requests (return 410/404 or specific JSON error).
    status: pending
  - id: expose-expiry-metadata
    content: Update Attachment serializers in zerver/lib/attachments.py to include media_expires_at and is_media_expired fields.
    status: pending
  - id: implement-image-recompression
    content: Add logic in zerver/lib/thumbnail.py to recompress original images (WebP, max 2048px) on upload.
    status: pending
  - id: configure-settings-and-admin
    content: Add MEDIA_RETENTION_DAYS and compression settings in zproject/default_settings.py and expose in Admin UI.
    status: pending
  - id: testing-and-migration
    content: Create migrations for model changes, backfill existing data, and add unit/integration tests for retention and compression.
    status: pending
isProject: false
---

# Media Retention and Compression Policy

## 1. Policy Overview

- **Scope**: Only uploaded media/files (attachments) are auto-deleted; messages themselves remain, and so do Attachment rows + URLs (WhatsApp-style).
- **Default window**: ~2 months (e.g., 60 days).
- **Behavior after expiry**:
    - File content is deleted from storage; Attachment row remains.
    - Download URL returns "media no longer available" (HTTP 410/404 + clear JSON).
    - Clients show a placeholder bubble with filename and an "expired" indicator.
- **Configuration**:
    - Global setting `MEDIA_RETENTION_DAYS` in `zproject/default_settings.py`.
    - Optionally allow per-realm override in realm settings.

## 2. Data Model Changes

**File**: `zerver/models/messages.py`

### `Attachment` / `ArchivedAttachment`

Add fields:

- `media_expires_at` (datetime): When physical file should be deleted.
- `deleted_from_storage` (bool, default False): Whether the file has been removed from backend.
- `deleted_at` (datetime, optional): For audit/debug.

*Note*: `ImageAttachment` does not need schema changes but depends on main `Attachment` lifecycle.

## 3. Setting Expiry on Upload

**File**: `zerver/lib/upload/__init__.py`

In `create_attachment()` / `upload_message_attachment()`:

- Compute retention period: `now + timedelta(days=retention_days)`.
- Use realm-specific retention if available, fallback to `MEDIA_RETENTION_DAYS`.
- Set `media_expires_at` on the new `Attachment`.
- Ensure preservation during TUS uploads (`zerver/views/tusd.py`) and message editing.

## 4. Storage Cleanup Job (Media-Only Retention)

**File**: `zerver/lib/retention.py`

Add helper `delete_expired_media_files()`:

1.  Query `Attachment` where `media_expires_at <= now()` and `deleted_from_storage = False`.
2.  Batch process (e.g., 100-1000 rows).
3.  For each attachment:

    - Delete main file via active `ZulipUploadBackend`.
    - Delete all derived thumbnails (using `zerver/lib/thumbnail.py` helpers).
    - Mark `deleted_from_storage = True`, set `deleted_at = now()`.

**Integration**:

- Wire into `zerver/management/commands/archive_messages.py` or create new command `delete_expired_media_files`.
- Ensure it runs independently of message retention.

## 5. Serving Behavior for Expired Media

**File**: `zerver/views/upload.py`

In `serve_file_backend()` / `serve_file()`:

- Check if `deleted_from_storage` is True or (`media_expires_at` is set and < now).
- **Response**:
    - Browser/HTML: HTTP 410 Gone (or 404) with "Media no longer available" template.
    - API/JSON: Error payload `{code: "MEDIA_EXPIRED", is_expired: true, ...}`.
- **Backend specifics**:
    - S3: Do not generate presigned URL if expired.
    - Local: Do not issue X-Accel-Redirect if expired.

## 6. Exposing Expiry Metadata to Clients

**Files**: `zerver/lib/attachments.py`, `zerver/views/*`

- **Attachment APIs**: Add `media_expires_at` and `is_media_expired` to serializers.
- **Message APIs**: Include these flags so clients can show "expired" UI and disable download links.

## 7. Compression Strategy

**Goal**: Best quality with low space, avoiding regressions for non-images.

### A. Image Recompression

**File**: `zerver/lib/thumbnail.py` (or new helper)

- New helper `recompress_original_image_if_needed(attachment, file_handle)`:
    - Only for safe image types (jpeg, png, heic). Skip SVG, ICO, etc.
    - Logic:
        - Downscale to max resolution (e.g., 2048px longest side) using `pyvips`.
        - Encode as WebP (quality ~75-80).
        - Replace original content with recompressed version.
        - Update `Attachment.size` and file extension if needed.
    - Hook: Call before `maybe_thumbnail()`.

### B. Non-Image Media

- Videos, audio, docs (PDF, ZIP) remain unchanged.
- Relies on retention policy (Section 4) to reclaim space.

### C. HTTP-Level

- Rely on Nginx for gzip/brotli of text assets (JSON, HTML, JS).
- Avoid re-compressing compressed media.

## 8. Configuration & Admin

**File**: `zproject/default_settings.py`

- `MEDIA_RETENTION_DAYS = 60` (default).
- `MEDIA_IMAGE_RECOMPRESS = True`.
- `MEDIA_IMAGE_MAX_DIMENSION = 2048`.
- `MEDIA_IMAGE_WEBP_QUALITY = 80`.
- **Admin UI**: Expose realm overrides and compression toggles.

## 9. Testing & Migration

- **Migration**: Add columns to `Attachment`/`ArchivedAttachment`. Backfill `media_expires_at` for existing rows (e.g., `create_time + 60 days` or NULL).
- **Tests**:
    - Unit: Expiry calculation, cleanup job logic, serving status codes, recompression quality/sizing.
    - Integration: End-to-end upload -> expire -> check availability.