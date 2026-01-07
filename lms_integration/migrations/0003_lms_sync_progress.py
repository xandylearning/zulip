# Generated migration for LMSSyncProgress model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0001_squashed_0569'),
        ('lms_integration', '0002_lms_admin_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='LMSSyncProgress',
            fields=[
                ('sync_id', models.CharField(help_text='Unique identifier for this sync operation', max_length=255, primary_key=True, serialize=False)),
                ('sync_type', models.CharField(choices=[('all', 'All Users'), ('students', 'Students Only'), ('mentors', 'Mentors Only'), ('batches', 'Batches Only')], help_text='Type of sync being performed', max_length=20)),
                ('current_stage', models.CharField(choices=[('initializing', 'Initializing'), ('counting_records', 'Counting Records'), ('syncing_students', 'Syncing Students'), ('syncing_mentors', 'Syncing Mentors'), ('syncing_batches', 'Syncing Batches'), ('updating_mappings', 'Updating User Mappings'), ('finalizing', 'Finalizing'), ('completed', 'Completed'), ('failed', 'Failed')], default='initializing', help_text='Current stage of the sync operation', max_length=50)),
                ('total_records', models.IntegerField(default=0, help_text='Total number of records to process')),
                ('processed_records', models.IntegerField(default=0, help_text='Number of records processed so far')),
                ('created_count', models.IntegerField(default=0)),
                ('updated_count', models.IntegerField(default=0)),
                ('skipped_count', models.IntegerField(default=0)),
                ('error_count', models.IntegerField(default=0)),
                ('status_message', models.CharField(default='', help_text='Current status message displayed to user', max_length=500)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_error', models.TextField(blank=True, help_text='Last error message if sync failed', null=True)),
                ('realm', models.ForeignKey(help_text='The realm this sync is for', on_delete=django.db.models.deletion.CASCADE, to='zerver.realm')),
                ('triggered_by', models.ForeignKey(blank=True, help_text='The admin user who triggered this sync', null=True, on_delete=django.db.models.deletion.SET_NULL, to='zerver.userprofile')),
            ],
            options={
                'db_table': 'lms_sync_progress',
                'ordering': ['-started_at'],
                'managed': True,
            },
        ),
        migrations.AddIndex(
            model_name='lmssyncprogress',
            index=models.Index(fields=['realm', '-started_at'], name='lms_integrat_realm_i_b2ee8a_idx'),
        ),
        migrations.AddIndex(
            model_name='lmssyncprogress',
            index=models.Index(fields=['current_stage'], name='lms_integrat_current_e05a4b_idx'),
        ),
    ]