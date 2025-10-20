# Generated migration for robust calls system enhancements

import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0001_initial'),
        ('zulip_calls_plugin', '0004_add_heartbeat_fields'),
    ]

    operations = [
        # Add moderator field to Call model
        migrations.AddField(
            model_name='call',
            name='moderator',
            field=models.ForeignKey(
                blank=True,
                help_text='User who initiated the call and has moderator privileges',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='moderated_calls',
                to='zerver.userprofile'
            ),
        ),
        
        # Add is_missed_notified field to Call model
        migrations.AddField(
            model_name='call',
            name='is_missed_notified',
            field=models.BooleanField(
                default=False,
                help_text='Whether missed call notification has been sent'
            ),
        ),
        
        # Add participant_left event type to CallEvent
        migrations.AlterField(
            model_name='callevent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('initiated', 'Call Initiated'),
                    ('ringing', 'Call Ringing'),
                    ('accepted', 'Call Accepted'),
                    ('declined', 'Call Declined'),
                    ('missed', 'Call Missed'),
                    ('ended', 'Call Ended'),
                    ('cancelled', 'Call Cancelled'),
                    ('participant_left', 'Participant Left'),
                ],
                max_length=20
            ),
        ),
        
        # Create CallQueue model
        migrations.CreateModel(
            name='CallQueue',
            fields=[
                ('queue_id', models.UUIDField(
                    db_index=True,
                    default=uuid.uuid4,
                    primary_key=True,
                    serialize=False
                )),
                ('call_type', models.CharField(
                    choices=[('video', 'Video Call'), ('audio', 'Audio Call')],
                    max_length=10
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('expired', 'Expired'),
                        ('converted', 'Converted to Call'),
                        ('cancelled', 'Cancelled'),
                    ],
                    default='pending',
                    max_length=20
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('notified_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('converted_to_call_id', models.UUIDField(blank=True, null=True)),
                ('busy_user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='queued_calls_received',
                    to='zerver.userprofile'
                )),
                ('caller', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='queued_calls_sent',
                    to='zerver.userprofile'
                )),
                ('realm', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='zerver.realm'
                )),
            ],
            options={
                'ordering': ['created_at'],
                'app_label': 'zulip_calls_plugin',
            },
        ),
        
        # Add index for cursor-based pagination on Call model
        migrations.AddIndex(
            model_name='call',
            index=models.Index(
                fields=['-created_at', 'call_id'],
                name='call_history_cursor_idx'
            ),
        ),
        
        # Add indexes for CallQueue model
        migrations.AddIndex(
            model_name='callqueue',
            index=models.Index(
                fields=['busy_user', 'status'],
                name='queue_user_status_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='callqueue',
            index=models.Index(
                fields=['status', 'expires_at'],
                name='queue_expiry_idx'
            ),
        ),
    ]

