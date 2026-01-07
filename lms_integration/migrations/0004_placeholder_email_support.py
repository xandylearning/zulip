# Generated for LMS Integration - Placeholder Email Support
# This migration helps manage existing users when implementing placeholder email support

from django.db import migrations
from django.core.management import CommandError


def create_placeholder_email_management_commands(apps, schema_editor):
    """
    Create placeholder email management utilities.
    This is a data migration that doesn't change schema but sets up
    management capabilities for placeholder emails.
    """
    # We don't actually need to do anything here in the migration itself
    # The functionality is implemented in the new modules we created
    pass


def reverse_placeholder_email_management(apps, schema_editor):
    """
    Reverse the placeholder email management setup.
    This doesn't actually remove any data, just indicates the migration was reversed.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('lms_integration', '0003_lms_sync_progress'),
    ]

    operations = [
        migrations.RunPython(
            create_placeholder_email_management_commands,
            reverse_placeholder_email_management,
        ),
    ]