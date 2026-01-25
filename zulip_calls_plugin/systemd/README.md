# Systemd Timer Configuration for Call Cleanup

This directory contains systemd service and timer configuration files for running the call cleanup task periodically.

## Files

- `zulip-call-cleanup.service` - The service unit that runs the cleanup command
- `zulip-call-cleanup.timer` - The timer unit that triggers the service every 30 seconds

## Installation (Production)

1. Copy the service and timer files to systemd:
   ```bash
   sudo cp zulip_calls_plugin/systemd/zulip-call-cleanup.* /etc/systemd/system/
   ```

2. Reload systemd:
   ```bash
   sudo systemctl daemon-reload
   ```

3. Enable and start the timer:
   ```bash
   sudo systemctl enable zulip-call-cleanup.timer
   sudo systemctl start zulip-call-cleanup.timer
   ```

4. Verify the timer is active:
   ```bash
   sudo systemctl status zulip-call-cleanup.timer
   sudo systemctl list-timers zulip-call-cleanup.timer
   ```

## Monitoring

### Check timer status
```bash
sudo systemctl status zulip-call-cleanup.timer
```

### View recent cleanup runs
```bash
sudo journalctl -u zulip-call-cleanup.service -n 50
```

### View real-time logs
```bash
sudo journalctl -u zulip-call-cleanup.service -f
```

## Development/Testing

For development, you can run the cleanup manually:

```bash
./manage.py cleanup_calls -v 2
```

Or trigger it once via systemd:

```bash
sudo systemctl start zulip-call-cleanup.service
```

## Alternative: Cron Configuration

If you prefer using cron instead of systemd timers, add this to the zulip user's crontab:

```cron
# Run call cleanup every 30 seconds
* * * * * cd /home/zulip/deployments/current && ./manage.py cleanup_calls >> /var/log/zulip/call-cleanup.log 2>&1
* * * * * sleep 30 && cd /home/zulip/deployments/current && ./manage.py cleanup_calls >> /var/log/zulip/call-cleanup.log 2>&1
```

## Worker Architecture

The cleanup process uses Zulip's RabbitMQ worker infrastructure:

1. **Management Command** (`cleanup_calls.py`): Enqueues cleanup events to the `call_cleanup` queue
2. **Worker** (`CallCleanupWorker` in `worker.py`): Processes events from the queue
3. **Periodic Trigger**: Systemd timer or cron runs the management command every 30 seconds

This architecture provides:
- **Resilience**: If the worker is down, events queue up and are processed when it restarts
- **Monitoring**: Worker status visible in Zulip's worker monitoring
- **Scalability**: Can run multiple workers if needed
- **Consistency**: Uses Zulip's standard queuing patterns

## Disabling

To disable the automatic cleanup:

```bash
sudo systemctl stop zulip-call-cleanup.timer
sudo systemctl disable zulip-call-cleanup.timer
```

## Customization

### Change cleanup frequency

Edit `/etc/systemd/system/zulip-call-cleanup.timer` and modify the `OnUnitActiveSec` value:

- Every minute: `OnUnitActiveSec=1m`
- Every 15 seconds: `OnUnitActiveSec=15s`
- Every 2 minutes: `OnUnitActiveSec=2m`

After changing, reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart zulip-call-cleanup.timer
```

### Old call cleanup

To periodically delete old ended calls (older than 30 days), modify the service file to include the cleanup flag:

```ini
ExecStart=/home/zulip/deployments/current/manage.py cleanup_calls --cleanup-old-calls --old-calls-days=30
```

Or run it separately as a daily cron job:
```cron
0 2 * * * cd /home/zulip/deployments/current && ./manage.py cleanup_calls --cleanup-old-calls --old-calls-days=30
```
