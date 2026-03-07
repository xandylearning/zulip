# Zulip Calls Plugin — Development

Quick reference for developing and testing the plugin.

## Running locally

```bash
python manage.py install_calls_plugin
./tools/run-dev
```

See [TESTING_GUIDE.md](./TESTING_GUIDE.md) for testing the embedded call UI and API.

## Feature flags (dev defaults)

| Setting | Default | Purpose |
|--------|---------|---------|
| `JITSI_JWT_ENABLED` | `False` | Jitsi room JWT auth; enable when Prosody JWT is configured. |
| `CALL_RECORDING_ENABLED` | `False` | GCP/Jibri recording; enable when recording is set up. |

Configure in Django settings or via plugin defaults in [plugin_config.py](./plugin_config.py). Details: [docs/JITSI_SECURITY_AND_RECORDING.md](./docs/JITSI_SECURITY_AND_RECORDING.md).

## Plugin layout

```
zulip_calls_plugin/
├── plugin_config.py      # Config and default settings (JWT, recording, Jitsi URL)
├── models/               # Call, CallEvent, GroupCall, GroupCallParticipant
├── views/calls.py        # All call API handlers
├── urls/calls.py         # URL routes
├── actions.py            # Event helpers (do_send_call_event, etc.)
├── worker.py             # Cleanup (stale calls, missed-call events)
├── templates/            # embedded_call.html, etc.
├── docs/                 # Flutter guide, Jitsi security/recording
├── CHANGELOG.md          # Version history
├── README.md             # Install, config, API summary
├── TESTING_GUIDE.md      # Dev testing steps
└── DOCUMENTATION_INDEX.md # Doc index
```

## Key docs

| Doc | Use |
|-----|-----|
| [README.md](./README.md) | Install, config, API table, Flutter summary |
| [CHANGELOG.md](./CHANGELOG.md) | What changed per version |
| [TESTING_GUIDE.md](./TESTING_GUIDE.md) | How to test embedded and API calls |
| [docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md](./docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md) | Mobile: APIs, events, UX, edge cases |
| [docs/JITSI_SECURITY_AND_RECORDING.md](./docs/JITSI_SECURITY_AND_RECORDING.md) | JWT and GCP recording setup |
| [API_REFERENCE.md](./API_REFERENCE.md) | Detailed API reference (see README for current behavior) |

## Making changes

- **Models**: Edit `models/calls.py`, then `python manage.py makemigrations zulip_calls_plugin`.
- **API**: Add or change handlers in `views/calls.py` and register routes in `urls/calls.py`.
- **Events**: Use helpers in `actions.py` and send via `send_event_on_commit`.
- **Cleanup**: Logic in `views/calls.py` (`cleanup_stale_calls`); scheduled via `worker.py`.

After edits, run tests and lint as per Zulip’s contribution guidelines.
