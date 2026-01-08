# Generated LMS Integration DM Permission Matrix Migration
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0001_initial'),
        ('lms_integration', '0004_placeholder_email_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='RealmDMPermissionMatrix',
            fields=[
                ('realm', models.OneToOneField(
                    help_text='The Zulip realm this permission matrix applies to',
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True,
                    serialize=False,
                    to='zerver.realm'
                )),
                ('enabled', models.BooleanField(
                    default=False,
                    help_text='Whether role-based DM restrictions are enabled for this realm'
                )),
                ('permission_matrix', models.JSONField(
                    default=dict,
                    help_text='Permission matrix defining which roles can see/DM which other roles'
                )),
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
                'db_table': 'lms_dm_permission_matrix',
                'managed': True,
            },
        ),
    ]

