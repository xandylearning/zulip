from datetime import timedelta

from django.conf import settings
from django.db import migrations, models
from django.utils.timezone import now as timezone_now


def backfill_media_expires_at(apps, schema_editor) -> None:
    Attachment = apps.get_model("zerver", "Attachment")
    ArchivedAttachment = apps.get_model("zerver", "ArchivedAttachment")

    # Use the global default retention window for backfill. Installations
    # that want a different policy can adjust per-realm configuration
    # going forward.
    retention_days = getattr(settings, "MEDIA_RETENTION_DAYS", 60)
    if retention_days is None or retention_days <= 0:
        # Treat non-positive values as "no automatic expiry" for backfill.
        return

    expires_delta = timedelta(days=retention_days)

    for model in (Attachment, ArchivedAttachment):
        # Only backfill rows that don't already have an explicit expiry.
        qs = model.objects.filter(media_expires_at__isnull=True)
        for row in qs.iterator():
            row.media_expires_at = row.create_time + expires_delta
            row.save(update_fields=["media_expires_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "10007_add_broadcast_button_click_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="attachment",
            name="media_expires_at",
            field=models.DateTimeField(null=True, db_index=True),
        ),
        migrations.AddField(
            model_name="attachment",
            name="deleted_from_storage",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="attachment",
            name="deleted_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="archivedattachment",
            name="media_expires_at",
            field=models.DateTimeField(null=True, db_index=True),
        ),
        migrations.AddField(
            model_name="archivedattachment",
            name="deleted_from_storage",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="archivedattachment",
            name="deleted_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(backfill_media_expires_at, migrations.RunPython.noop),
    ]

