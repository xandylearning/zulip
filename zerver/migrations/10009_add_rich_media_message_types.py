# Generated migration for rich media message types

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "10008_attachment_media_retention_fields"),
    ]

    operations = [
        # Update MessageType choices to include new media types
        migrations.AlterField(
            model_name="archivedmessage",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Normal"),
                    (2, "Resolve Topic Notification"),
                    (3, "Image"),
                    (4, "Video"),
                    (5, "Audio"),
                    (6, "Document"),
                    (7, "Location"),
                    (8, "Contact"),
                    (9, "Sticker"),
                    (10, "Voice Message"),
                ],
                db_default=1,
                default=1,
            ),
        ),
        migrations.AlterField(
            model_name="message",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Normal"),
                    (2, "Resolve Topic Notification"),
                    (3, "Image"),
                    (4, "Video"),
                    (5, "Audio"),
                    (6, "Document"),
                    (7, "Location"),
                    (8, "Contact"),
                    (9, "Sticker"),
                    (10, "Voice Message"),
                ],
                db_default=1,
                default=1,
            ),
        ),
        # Add caption field
        migrations.AddField(
            model_name="archivedmessage",
            name="caption",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="caption",
            field=models.TextField(blank=True, null=True),
        ),
        # Add primary_attachment foreign key
        migrations.AddField(
            model_name="archivedmessage",
            name="primary_attachment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="archivedmessage_primary_messages",
                to="zerver.attachment",
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="primary_attachment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="message_primary_messages",
                to="zerver.attachment",
            ),
        ),
        # Add media_metadata JSON field
        migrations.AddField(
            model_name="archivedmessage",
            name="media_metadata",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="media_metadata",
            field=models.JSONField(blank=True, null=True),
        ),
        # Add index on type field for filtering by media type
        migrations.AddIndex(
            model_name="message",
            index=models.Index(fields=["type"], name="zerver_message_type_idx"),
        ),
    ]
