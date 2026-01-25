# Generated migration for group call support

import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0001_initial'),
        ('zulip_calls_plugin', '0005_add_moderator_and_queue'),
    ]

    operations = [
        # Create GroupCall model
        migrations.CreateModel(
            name='GroupCall',
            fields=[
                ('call_id', models.UUIDField(
                    db_index=True,
                    default=uuid.uuid4,
                    primary_key=True,
                    serialize=False
                )),
                ('call_type', models.CharField(
                    choices=[('video', 'Video Call'), ('audio', 'Audio Call')],
                    max_length=10
                )),
                ('state', models.CharField(
                    choices=[('active', 'Active'), ('ended', 'Ended')],
                    default='active',
                    max_length=20
                )),
                ('jitsi_room_name', models.CharField(max_length=255)),
                ('jitsi_room_url', models.URLField()),
                ('max_participants', models.IntegerField(default=50)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('topic', models.CharField(blank=True, max_length=255, null=True)),
                ('host', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='hosted_group_calls',
                    to='zerver.userprofile'
                )),
                ('realm', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='zerver.realm'
                )),
                ('stream', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='zerver.stream'
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'app_label': 'zulip_calls_plugin',
            },
        ),

        # Create GroupCallParticipant model
        migrations.CreateModel(
            name='GroupCallParticipant',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('state', models.CharField(
                    choices=[
                        ('invited', 'Invited'),
                        ('ringing', 'Ringing'),
                        ('joined', 'Joined'),
                        ('declined', 'Declined'),
                        ('left', 'Left'),
                        ('missed', 'Missed'),
                    ],
                    default='invited',
                    max_length=20
                )),
                ('is_host', models.BooleanField(default=False)),
                ('invited_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('joined_at', models.DateTimeField(blank=True, null=True)),
                ('left_at', models.DateTimeField(blank=True, null=True)),
                ('last_heartbeat', models.DateTimeField(blank=True, null=True)),
                ('call', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='participants',
                    to='zulip_calls_plugin.groupcall'
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='group_call_participations',
                    to='zerver.userprofile'
                )),
            ],
            options={
                'app_label': 'zulip_calls_plugin',
            },
        ),

        # Add unique constraint for GroupCallParticipant
        migrations.AlterUniqueTogether(
            name='groupcallparticipant',
            unique_together={('call', 'user')},
        ),

        # Add indexes for GroupCall model
        migrations.AddIndex(
            model_name='groupcall',
            index=models.Index(
                fields=['host'],
                name='group_call_host_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='groupcall',
            index=models.Index(
                fields=['state'],
                name='group_call_state_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='groupcall',
            index=models.Index(
                fields=['created_at'],
                name='group_call_created_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='groupcall',
            index=models.Index(
                fields=['stream', 'topic'],
                name='group_call_stream_topic_idx'
            ),
        ),

        # Add indexes for GroupCallParticipant model
        migrations.AddIndex(
            model_name='groupcallparticipant',
            index=models.Index(
                fields=['call', 'state'],
                name='group_participant_call_state_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='groupcallparticipant',
            index=models.Index(
                fields=['user', 'state'],
                name='group_participant_user_state_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='groupcallparticipant',
            index=models.Index(
                fields=['call', 'last_heartbeat'],
                name='group_participant_heartbeat_idx'
            ),
        ),
    ]
