from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('zulip_calls_plugin', '0003_remove_call_zulip_calls_state_27122d_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='last_heartbeat_sender',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='call',
            name='last_heartbeat_receiver',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='call',
            name='is_backgrounded',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='call',
            name='state',
            field=models.CharField(
                choices=[
                    ('calling', 'Calling'),
                    ('ringing', 'Ringing'),
                    ('accepted', 'Accepted'),
                    ('rejected', 'Rejected'),
                    ('timeout', 'Timeout'),
                    ('ended', 'Ended'),
                    ('missed', 'Missed'),
                    ('cancelled', 'Cancelled'),
                    ('network_failure', 'Network Failure')
                ],
                default='calling',
                max_length=20
            ),
        ),
    ]
