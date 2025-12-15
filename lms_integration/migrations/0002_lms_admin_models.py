# Generated LMS Integration Admin Models Migration
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0001_initial'),
        ('lms_integration', '0001_initial'),  # Depend on existing LMS models
    ]

    operations = [
        migrations.CreateModel(
            name='LMSIntegrationConfig',
            fields=[
                ('realm', models.OneToOneField(
                    help_text='The Zulip realm this configuration applies to',
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True,
                    serialize=False,
                    to='zerver.realm'
                )),
                ('enabled', models.BooleanField(
                    default=False,
                    help_text='Whether LMS integration is enabled for this realm'
                )),
                ('lms_db_host', models.CharField(
                    default='',
                    help_text='LMS database host',
                    max_length=255
                )),
                ('lms_db_port', models.IntegerField(
                    default=5432,
                    help_text='LMS database port'
                )),
                ('lms_db_name', models.CharField(
                    default='',
                    help_text='LMS database name',
                    max_length=128
                )),
                ('lms_db_username', models.CharField(
                    default='',
                    help_text='LMS database username',
                    max_length=128
                )),
                ('lms_db_password', models.CharField(
                    default='',
                    help_text='LMS database password (encrypted)',
                    max_length=255
                )),
                ('webhook_secret', models.CharField(
                    default='',
                    help_text='Secret for webhook authentication',
                    max_length=255
                )),
                ('jwt_enabled', models.BooleanField(
                    default=False,
                    help_text='Whether JWT authentication is enabled'
                )),
                ('testpress_api_url', models.URLField(
                    default='',
                    help_text='TestPress API base URL for JWT validation'
                )),
                ('activity_monitor_enabled', models.BooleanField(
                    default=False,
                    help_text='Whether activity monitoring is enabled'
                )),
                ('poll_interval', models.IntegerField(
                    default=60,
                    help_text='Activity polling interval in seconds'
                )),
                ('notify_mentors', models.BooleanField(
                    default=True,
                    help_text='Whether to send notifications to mentors'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    help_text='The admin user who last updated this configuration',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='zerver.userprofile'
                )),
            ],
            options={
                'db_table': 'lms_integration_config',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='LMSSyncHistory',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('sync_type', models.CharField(
                    choices=[
                        ('all', 'All Users'),
                        ('students', 'Students Only'),
                        ('mentors', 'Mentors Only'),
                    ],
                    help_text='Type of sync performed',
                    max_length=20
                )),
                ('users_created', models.IntegerField(default=0)),
                ('users_updated', models.IntegerField(default=0)),
                ('users_skipped', models.IntegerField(default=0)),
                ('users_errors', models.IntegerField(default=0)),
                ('batches_synced', models.IntegerField(default=0)),
                ('batch_sync_enabled', models.BooleanField(default=False)),
                ('batch_sync_error', models.TextField(blank=True, null=True)),
                ('started_at', models.DateTimeField()),
                ('completed_at', models.DateTimeField()),
                ('duration_seconds', models.FloatField(
                    help_text='Total sync duration in seconds'
                )),
                ('status', models.CharField(
                    choices=[
                        ('success', 'Success'),
                        ('partial', 'Partial Success'),
                        ('failed', 'Failed'),
                    ],
                    default='success',
                    max_length=20
                )),
                ('error_message', models.TextField(blank=True, null=True)),
                ('trigger_type', models.CharField(
                    choices=[
                        ('manual', 'Manual'),
                        ('webhook', 'Webhook'),
                        ('scheduled', 'Scheduled'),
                    ],
                    default='manual',
                    max_length=20
                )),
                ('realm', models.ForeignKey(
                    help_text='The realm this sync was performed for',
                    on_delete=django.db.models.deletion.CASCADE,
                    to='zerver.realm'
                )),
                ('triggered_by', models.ForeignKey(
                    blank=True,
                    help_text='The admin user who triggered this sync',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='zerver.userprofile'
                )),
            ],
            options={
                'db_table': 'lms_sync_history',
                'ordering': ['-started_at'],
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='LMSAdminLog',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('level', models.CharField(
                    choices=[
                        ('DEBUG', 'Debug'),
                        ('INFO', 'Info'),
                        ('WARNING', 'Warning'),
                        ('ERROR', 'Error'),
                        ('CRITICAL', 'Critical'),
                    ],
                    default='INFO',
                    max_length=10
                )),
                ('source', models.CharField(
                    choices=[
                        ('user_sync', 'User Sync'),
                        ('activity_monitor', 'Activity Monitor'),
                        ('webhook', 'Webhook'),
                        ('jwt_auth', 'JWT Auth'),
                        ('admin_ui', 'Admin UI'),
                        ('configuration', 'Configuration'),
                        ('database', 'Database'),
                        ('system', 'System'),
                    ],
                    help_text='The component that generated this log',
                    max_length=50
                )),
                ('message', models.TextField(help_text='The log message')),
                ('details', models.JSONField(
                    blank=True,
                    help_text='Additional structured data for this log entry',
                    null=True
                )),
                ('exception_type', models.CharField(
                    blank=True,
                    help_text='Exception class name if this is an error',
                    max_length=255,
                    null=True
                )),
                ('stack_trace', models.TextField(
                    blank=True,
                    help_text='Full stack trace if this is an error',
                    null=True
                )),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('realm', models.ForeignKey(
                    blank=True,
                    help_text='The realm this log entry relates to',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='zerver.realm'
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    help_text='The user who triggered this action (if applicable)',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='zerver.userprofile'
                )),
            ],
            options={
                'db_table': 'lms_admin_logs',
                'ordering': ['-timestamp'],
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='LMSUserMapping',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('lms_user_id', models.IntegerField(help_text='LMS user ID')),
                ('lms_user_type', models.CharField(
                    choices=[
                        ('student', 'Student'),
                        ('mentor', 'Mentor'),
                    ],
                    help_text='Type of user in the LMS',
                    max_length=10
                )),
                ('lms_username', models.CharField(
                    help_text='Username in the LMS',
                    max_length=255
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_synced_at', models.DateTimeField(auto_now=True)),
                ('sync_count', models.IntegerField(
                    default=1,
                    help_text='Number of times this user has been synced'
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Whether this mapping is currently active'
                )),
                ('last_error', models.TextField(
                    blank=True,
                    help_text='Last error encountered during sync',
                    null=True
                )),
                ('zulip_user', models.OneToOneField(
                    help_text='The Zulip user',
                    on_delete=django.db.models.deletion.CASCADE,
                    to='zerver.userprofile'
                )),
            ],
            options={
                'db_table': 'lms_user_mapping',
                'managed': True,
            },
        ),
        # Add indexes
        migrations.AddIndex(
            model_name='lmssynchistory',
            index=models.Index(fields=['realm', '-started_at'], name='lms_sync_hist_realm_started_idx'),
        ),
        migrations.AddIndex(
            model_name='lmssynchistory',
            index=models.Index(fields=['sync_type'], name='lms_sync_hist_type_idx'),
        ),
        migrations.AddIndex(
            model_name='lmssynchistory',
            index=models.Index(fields=['status'], name='lms_sync_hist_status_idx'),
        ),
        migrations.AddIndex(
            model_name='lmsadminlog',
            index=models.Index(fields=['realm', '-timestamp'], name='lms_admin_log_realm_time_idx'),
        ),
        migrations.AddIndex(
            model_name='lmsadminlog',
            index=models.Index(fields=['level'], name='lms_admin_log_level_idx'),
        ),
        migrations.AddIndex(
            model_name='lmsadminlog',
            index=models.Index(fields=['source'], name='lms_admin_log_source_idx'),
        ),
        migrations.AddIndex(
            model_name='lmsadminlog',
            index=models.Index(fields=['timestamp'], name='lms_admin_log_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='lmsusermapping',
            index=models.Index(fields=['lms_user_id', 'lms_user_type'], name='lms_user_map_lms_user_idx'),
        ),
        migrations.AddIndex(
            model_name='lmsusermapping',
            index=models.Index(fields=['zulip_user'], name='lms_user_map_zulip_user_idx'),
        ),
        migrations.AddIndex(
            model_name='lmsusermapping',
            index=models.Index(fields=['last_synced_at'], name='lms_user_map_last_sync_idx'),
        ),
        # Add unique constraint
        migrations.AddConstraint(
            model_name='lmsusermapping',
            constraint=models.UniqueConstraint(
                fields=['lms_user_id', 'lms_user_type'],
                name='lms_user_mapping_unique_lms_user'
            ),
        ),
    ]