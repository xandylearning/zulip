# Generated migration for enhanced call model
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('zulip_calls_plugin', '0001_initial'),
    ]

    operations = [
        # Update call states to match the new implementation
        migrations.RunSQL(
            "UPDATE zulip_calls_plugin_call SET state = 'calling' WHERE state = 'initiated';",
            reverse_sql="UPDATE zulip_calls_plugin_call SET state = 'initiated' WHERE state = 'calling';"
        ),

        # Add new field jitsi_room_id if it doesn't already exist
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'jitsi_room_id'
    ) THEN
        ALTER TABLE zulip_calls_plugin_call ADD COLUMN jitsi_room_id varchar(100);
    END IF;
END
$$;
                    """,
                    reverse_sql="""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'jitsi_room_id'
    ) THEN
        ALTER TABLE zulip_calls_plugin_call DROP COLUMN jitsi_room_id;
    END IF;
END
$$;
                    """,
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name='call',
                    name='jitsi_room_id',
                    field=models.CharField(max_length=100, null=True, blank=True),
                ),
            ],
        ),

        # Rename fields for consistency (conditional at DB level)
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'initiator_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'sender_id'
    ) THEN
        ALTER TABLE zulip_calls_plugin_call RENAME COLUMN initiator_id TO sender_id;
    END IF;
END
$$;
                    """,
                    reverse_sql="""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'sender_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'initiator_id'
    ) THEN
        ALTER TABLE zulip_calls_plugin_call RENAME COLUMN sender_id TO initiator_id;
    END IF;
END
$$;
                    """,
                ),
                migrations.RunSQL(
                    """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'recipient_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'receiver_id'
    ) THEN
        ALTER TABLE zulip_calls_plugin_call RENAME COLUMN recipient_id TO receiver_id;
    END IF;
END
$$;
                    """,
                    reverse_sql="""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'receiver_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'recipient_id'
    ) THEN
        ALTER TABLE zulip_calls_plugin_call RENAME COLUMN receiver_id TO recipient_id;
    END IF;
END
$$;
                    """,
                ),
                migrations.RunSQL(
                    """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'started_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'answered_at'
    ) THEN
        ALTER TABLE zulip_calls_plugin_call RENAME COLUMN started_at TO answered_at;
    END IF;
END
$$;
                    """,
                    reverse_sql="""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'answered_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zulip_calls_plugin_call' AND column_name = 'started_at'
    ) THEN
        ALTER TABLE zulip_calls_plugin_call RENAME COLUMN answered_at TO started_at;
    END IF;
END
$$;
                    """,
                ),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name='call',
                    old_name='initiator',
                    new_name='sender',
                ),
                migrations.RenameField(
                    model_name='call',
                    old_name='recipient',
                    new_name='receiver',
                ),
                migrations.RenameField(
                    model_name='call',
                    old_name='started_at',
                    new_name='answered_at',
                ),
            ],
        ),

        # Update related names (no-op at DB level; kept for state correctness)
        migrations.AlterField(
            model_name='call',
            name='sender',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name='calls_sent',
                to='zerver.userprofile'
            ),
        ),
        migrations.AlterField(
            model_name='call',
            name='receiver',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name='calls_received',
                to='zerver.userprofile'
            ),
        ),

        # Update indexes
        migrations.RunSQL(
            "DROP INDEX IF EXISTS zulip_calls_plugin_call_state_created_at_idx;",
            reverse_sql="CREATE INDEX zulip_calls_plugin_call_state_created_at_idx ON zulip_calls_plugin_call (state, created_at);"
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS zulip_calls_plugin_call_initiator_created_at_idx;",
            reverse_sql="CREATE INDEX zulip_calls_plugin_call_initiator_created_at_idx ON zulip_calls_plugin_call (sender_id, created_at);"
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS zulip_calls_plugin_call_recipient_created_at_idx;",
            reverse_sql="CREATE INDEX zulip_calls_plugin_call_recipient_created_at_idx ON zulip_calls_plugin_call (receiver_id, created_at);"
        ),

        # Add new indexes (idempotent)
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS call_participants_idx ON zulip_calls_plugin_call (sender_id, receiver_id);",
            reverse_sql="DROP INDEX IF EXISTS call_participants_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS call_status_idx ON zulip_calls_plugin_call (state);",
            reverse_sql="DROP INDEX IF EXISTS call_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS call_created_at_idx ON zulip_calls_plugin_call (created_at);",
            reverse_sql="DROP INDEX IF EXISTS call_created_at_idx;"
        ),
    ]