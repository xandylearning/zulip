# AI Agent System Configuration

This comprehensive guide covers the complete configuration process for the LangGraph-based AI agent system with Portkey integration in Zulip, including the AI Mentor system for intelligent mentor-student interactions.

## Overview

The AI Agent system provides intelligent assistance through advanced AI agents that:

- Analyze conversation context and user needs
- Study communication styles from previous messages
- Generate appropriate responses that match user tone and expertise
- Send AI-generated responses on behalf of unavailable users
- Provide intelligent suggestions and recommendations

## Prerequisites

- Zulip Server 10.x or later
- Portkey AI Gateway account and API key
- Python dependencies for AI processing
- Sufficient server resources for AI processing

## Environment Variables Configuration

### Core AI Agent Settings

#### Essential Configuration

```bash
# Enable the AI agent system
USE_LANGGRAPH_AGENTS=true

# Portkey AI Gateway Configuration
PORTKEY_API_KEY=your_portkey_api_key_here
PORTKEY_BASE_URL=https://api.portkey.ai/v1
```

#### AI Model Configuration

```bash
# LLM Model Settings
AI_MENTOR_MODEL=gpt-4                    # AI model to use (gpt-4, gpt-3.5-turbo, etc.)
AI_MENTOR_TEMPERATURE=0.7               # Response creativity (0.0-1.0)
AI_MENTOR_MAX_TOKENS=1000               # Maximum response length

# System Performance
AI_MENTOR_MAX_RETRIES=3                 # Number of retry attempts on failure
AI_MENTOR_TIMEOUT=30                    # Request timeout in seconds
```

#### Decision Thresholds

```bash
# Time-based Settings (in minutes)
AI_MENTOR_MIN_ABSENCE_MINUTES=240       # Minimum mentor absence before AI responds (4 hours)
AI_MENTOR_MAX_DAILY_RESPONSES=3         # Maximum AI responses per mentor per day

# Quality Thresholds (0.0-1.0)
AI_MENTOR_URGENCY_THRESHOLD=0.7         # Minimum urgency score to trigger response
AI_MENTOR_CONFIDENCE_THRESHOLD=0.6      # Minimum confidence score to send response
```

#### Data Storage

```bash
# State Persistence
AI_AGENT_STATE_DB_PATH=/var/lib/zulip/ai_agent_state.db
```

### Advanced Configuration

#### Workflow Tuning

```bash
# Style Analysis
AI_STYLE_MIN_MESSAGES=5                 # Minimum messages required for style analysis
AI_STYLE_MAX_MESSAGES=50                # Maximum messages to analyze for style
AI_STYLE_CACHE_HOURS=24                 # Hours to cache style analysis

# Context Analysis
AI_CONTEXT_HISTORY_LIMIT=10             # Number of previous messages to consider
AI_URGENCY_KEYWORDS_WEIGHT=0.8          # Weight given to urgency keywords

# Response Generation
AI_RESPONSE_VARIANTS=3                  # Number of response variants to generate
AI_RESPONSE_QUALITY_THRESHOLD=0.7       # Minimum quality threshold for responses

# Suggestions
AI_MAX_SUGGESTIONS=5                    # Maximum number of suggestions to generate
```

#### Feature Flags

```bash
# Enable/Disable Features
AI_ENABLE_STYLE_ANALYSIS=true
AI_ENABLE_CONTEXT_ANALYSIS=true
AI_ENABLE_RESPONSE_GEN=true
AI_ENABLE_SUGGESTIONS=true
AI_ENABLE_AUTO_RESPONSES=true
```

#### Logging and Monitoring

```bash
# Logging Configuration
AI_LOG_INTERACTIONS=true               # Log all AI interactions
AI_LOG_LEVEL=INFO                      # Logging level (DEBUG, INFO, WARNING, ERROR)
AI_LOG_PERFORMANCE=true                # Log performance metrics
AI_LOG_DECISIONS=true                  # Log AI decision reasoning

# Analytics
AI_MENTOR_ANALYTICS_ENABLED=true       # Enable analytics collection
AI_MENTOR_NOTIFICATIONS_ENABLED=true   # Enable notification system
```

#### Security and Privacy

```bash
# Privacy Settings
AI_REQUIRE_CONSENT=true                # Require explicit user consent
AI_ANONYMIZE_LOGS=true                 # Anonymize logs for privacy
AI_MAX_CONTEXT_DAYS=30                 # Maximum days to retain context data

# Performance Monitoring
AI_ERROR_RATE_THRESHOLD=0.1            # Alert threshold for error rates
```

## Configuration Steps

### 1. Enable AI Mentor Worker

Add the following to `/etc/zulip/zulip.conf`:

```ini
[application_server]
ai_mentor_worker_enabled = true
```

### 2. Configure Secrets

Add your Portkey API key to `/etc/zulip/zulip-secrets.conf`:

```ini
[secrets]
portkey_api_key = your_actual_portkey_api_key_here
```

### 3. Configure Settings

Add the following configuration to `/etc/zulip/settings.py`:

```python
###############
# AI Agent System Configuration
###############

# Enable LangGraph-based AI agent system
USE_LANGGRAPH_AGENTS = True

# Portkey AI Gateway Configuration
PORTKEY_API_KEY = get_secret("portkey_api_key")

# AI Model Configuration
AI_MENTOR_MODEL = "gemini-1.5-flash"  # AI model to use
AI_MENTOR_TEMPERATURE = 0.7  # Response creativity (0.0-1.0)
AI_MENTOR_MAX_TOKENS = 1000  # Maximum response length
AI_MENTOR_MAX_RETRIES = 3  # Number of retry attempts on failure
AI_MENTOR_TIMEOUT = 30  # Request timeout in seconds

# Decision Thresholds (Production Values)
AI_MENTOR_MIN_ABSENCE_MINUTES = 240  # 4 hours minimum absence
AI_MENTOR_MAX_DAILY_RESPONSES = 3     # Max 3 AI responses per mentor per day
AI_MENTOR_URGENCY_THRESHOLD = 0.7     # High urgency required
AI_MENTOR_CONFIDENCE_THRESHOLD = 0.6  # High confidence required

# State Persistence
AI_AGENT_STATE_DB_PATH = "/var/lib/zulip/ai_agent_state.db"

# Feature Flags
AI_ENABLE_STYLE_ANALYSIS = True
AI_ENABLE_CONTEXT_ANALYSIS = True
AI_ENABLE_RESPONSE_GEN = True
AI_ENABLE_SUGGESTIONS = True
AI_ENABLE_AUTO_RESPONSES = True

# Logging and Monitoring
AI_LOG_INTERACTIONS = True  # Log all AI interactions
AI_LOG_LEVEL = "INFO"  # Logging level (DEBUG, INFO, WARNING, ERROR)
AI_LOG_PERFORMANCE = True  # Log performance metrics
AI_LOG_DECISIONS = True  # Log AI decision reasoning

# Security and Privacy
AI_REQUIRE_CONSENT = True  # Require explicit user consent
AI_ANONYMIZE_LOGS = True  # Anonymize logs for privacy
AI_MAX_CONTEXT_DAYS = 30  # Maximum days to retain context data
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_LANGGRAPH_AGENTS` | false | Enable AI agent system |
| `PORTKEY_API_KEY` | "" | Portkey API authentication key |
| `AI_MENTOR_MODEL` | gpt-4 | LLM model to use |
| `AI_MENTOR_TEMPERATURE` | 0.7 | Response creativity level |
| `AI_MENTOR_MIN_ABSENCE_MINUTES` | 240 | Minutes before AI responds |
| `AI_MENTOR_MAX_DAILY_RESPONSES` | 3 | Daily response limit per mentor |
| `AI_MENTOR_CONFIDENCE_THRESHOLD` | 0.6 | Minimum confidence to send |
| `AI_MENTOR_URGENCY_THRESHOLD` | 0.7 | Minimum urgency to trigger |
| `AI_AGENT_STATE_DB_PATH` | /tmp/ai_agent_state.db | State database location |

## Development vs Production Settings

### Development Environment

```bash
# Development-friendly settings
export DJANGO_ENVIRONMENT=development
export USE_LANGGRAPH_AGENTS=true
export AI_MENTOR_MIN_ABSENCE_MINUTES=5        # 5 minutes for testing
export AI_MENTOR_MAX_DAILY_RESPONSES=10       # More responses for testing
export AI_MENTOR_URGENCY_THRESHOLD=0.3        # Lower threshold for testing
export AI_MENTOR_CONFIDENCE_THRESHOLD=0.3     # Lower threshold for testing

# Optional for development without API keys
export PORTKEY_API_KEY=test_key_for_development
```

### Production Environment

```bash
# Production-optimized settings
export USE_LANGGRAPH_AGENTS=true
export AI_MENTOR_MIN_ABSENCE_MINUTES=240      # 4 hours for production
export AI_MENTOR_MAX_DAILY_RESPONSES=3        # Conservative limit
export AI_MENTOR_URGENCY_THRESHOLD=0.7        # Higher threshold
export AI_MENTOR_CONFIDENCE_THRESHOLD=0.6     # Higher confidence required
export PORTKEY_API_KEY=your_production_api_key
```

### 4. Create State Database Directory

```bash
sudo mkdir -p /var/lib/zulip
sudo chown zulip:zulip /var/lib/zulip
sudo chmod 755 /var/lib/zulip
```

### 5. Run Database Migrations

```bash
su zulip -c '/home/zulip/deployments/current/manage.py migrate'
```

### 6. Apply Configuration Changes

```bash
sudo /home/zulip/deployments/current/scripts/zulip-puppet-apply
```

### 7. Restart Services

```bash
su zulip -c '/home/zulip/deployments/current/scripts/restart-server'
```

## Validation and Troubleshooting

### Configuration Validation

The system automatically validates configuration on startup. Check logs for warnings:

```bash
# Check for configuration warnings
sudo tail -f /var/log/zulip/django.log | grep "AI Agent Configuration Warning"
```

### Common Issues

1. **Missing API Keys**: Ensure `PORTKEY_API_KEY` is set
2. **High Thresholds**: Lower confidence/urgency thresholds for testing
3. **State Database**: Ensure the AI state database path is writable
4. **Network Access**: Verify Portkey API connectivity from your server

### Testing Configuration

Run the AI integration test to validate your setup:

```bash
cd /srv/zulip
python test_ai_integration.py
```

### Quick Setup Commands

```bash
# Production setup
export USE_LANGGRAPH_AGENTS=true
export AI_MENTOR_MIN_ABSENCE_MINUTES=240
export PORTKEY_API_KEY=your_api_key

# Development setup
export USE_LANGGRAPH_AGENTS=true
export AI_MENTOR_MIN_ABSENCE_MINUTES=5
export AI_MENTOR_CONFIDENCE_THRESHOLD=0.3
export AI_MENTOR_URGENCY_THRESHOLD=0.3
```

## Configuration Options

### AI Model Settings

| Setting | Description | Default | Recommended |
|---------|-------------|---------|-------------|
| `AI_MENTOR_MODEL` | AI model to use | `gemini-1.5-flash` | `gemini-1.5-flash` or `gpt-4` |
| `AI_MENTOR_TEMPERATURE` | Response creativity (0.0-1.0) | `0.7` | `0.7` for balanced creativity |
| `AI_MENTOR_MAX_TOKENS` | Maximum response length | `1000` | `1000-2000` depending on needs |
| `AI_MENTOR_TIMEOUT` | Request timeout (seconds) | `30` | `30-60` for complex models |

### Decision Thresholds

| Setting | Description | Default | Production |
|---------|-------------|---------|------------|
| `AI_MENTOR_MIN_ABSENCE_MINUTES` | Minimum mentor absence before AI responds | `1` | `240` (4 hours) |
| `AI_MENTOR_MAX_DAILY_RESPONSES` | Max AI responses per mentor per day | `100` | `3` |
| `AI_MENTOR_URGENCY_THRESHOLD` | Minimum urgency score to trigger response | `0.0` | `0.7` |
| `AI_MENTOR_CONFIDENCE_THRESHOLD` | Minimum confidence score to send response | `0.01` | `0.6` |

### Feature Flags

| Setting | Description | Default |
|---------|-------------|---------|
| `AI_ENABLE_STYLE_ANALYSIS` | Enable mentor style analysis | `True` |
| `AI_ENABLE_CONTEXT_ANALYSIS` | Enable conversation context analysis | `True` |
| `AI_ENABLE_RESPONSE_GEN` | Enable AI response generation | `True` |
| `AI_ENABLE_SUGGESTIONS` | Enable intelligent suggestions | `True` |
| `AI_ENABLE_AUTO_RESPONSES` | Enable automatic responses | `True` |

## User Setup

### Setting Up Mentor Roles

Users need the `ROLE_MENTOR` role to receive AI assistance:

```python
# In Django shell or management command
from zerver.models import UserProfile
user = UserProfile.objects.get(email='mentor@example.com')
user.role = UserProfile.ROLE_MENTOR
user.save()
```

### Consent Management

Users can opt-in to AI assistance through their personal settings or organization
administrators can configure consent requirements.

## Monitoring and Logging

### Log Files

- **AI Mentor Worker**: `/var/log/zulip/ai_mentor_worker.log`
- **AI Agent Core**: `/var/log/zulip/ai_agent_core.log`
- **General Zulip logs**: `/var/log/zulip/`

### Health Checks

```bash
# Check if AI mentor worker is running
sudo supervisorctl status zulip-ai-mentor-worker

# Check logs
tail -f /var/log/zulip/ai_mentor_worker.log

# Test AI functionality
su zulip -c '/home/zulip/deployments/current/manage.py shell'
```

### Performance Monitoring

The system tracks:
- Response times
- Token usage
- Success rates
- Error rates

## Security Considerations

### Data Privacy

- **Realm isolation**: AI processing is isolated per organization
- **Consent requirements**: Users can opt-in to AI assistance
- **Log anonymization**: Personal data is anonymized in logs
- **Context retention limits**: Conversation history is automatically purged

### API Key Security

- Store Portkey API key in `/etc/zulip/zulip-secrets.conf`
- Use environment variables for sensitive configuration
- Enable log anonymization for privacy

## Troubleshooting

### Common Issues

1. **Worker not starting**: Check supervisor configuration and logs
2. **API key errors**: Verify Portkey API key is correct
3. **No AI responses**: Check decision thresholds and mentor absence time
4. **Performance issues**: Monitor resource usage and adjust timeouts

### Debug Mode

Enable debug logging for troubleshooting:

```python
# In settings.py for debugging
AI_LOG_LEVEL = "DEBUG"
AI_LOG_INTERACTIONS = True
AI_LOG_DECISIONS = True
```

### Testing Configuration

```python
# In Django shell
from zerver.actions.ai_mentor_events import trigger_ai_agent_conversation
from zerver.models import UserProfile

mentor = UserProfile.objects.get(email='mentor@example.com')
student = UserProfile.objects.get(email='student@example.com')

# Trigger test conversation
trigger_ai_agent_conversation(
    mentor=mentor,
    student=student,
    original_message="Hello, I need help with Python programming",
    original_message_id=12345
)
```

## Performance Tuning

### Resource Limits

```bash
# In /etc/zulip/zulip.conf
[application_server]
ai_mentor_worker_memory_limit = 512M
ai_mentor_worker_cpu_limit = 50
```

### Workflow Configuration

```python
# In settings.py for production optimization
AI_AGENT_WORKFLOW_CONFIG = {
    'style_analysis': {
        'min_messages_required': 5,  # Require more messages for analysis
        'max_messages_analyzed': 20,
        'cache_duration_hours': 24,  # Longer cache for production
    },
    'context_analysis': {
        'conversation_history_limit': 10,  # More context for better responses
        'urgency_keywords_weight': 0.5,
    },
    'response_generation': {
        'candidate_variants': 3,  # Generate multiple response options
        'quality_threshold': 0.7,  # Higher quality threshold
    }
}
```

## Support

For issues with the AI Agent system:

1. Check the logs in `/var/log/zulip/ai_mentor_worker.log`
2. Verify configuration in `/etc/zulip/settings.py`
3. Test with debug logging enabled
4. Contact support with specific error messages and logs

## Related Documentation

- [AI Integrations](ai-integrations.md) - General AI features overview
- [Production Settings](settings.md) - Server configuration
- [Security Model](security-model.md) - Security considerations
- [System Configuration](system-configuration.md) - System-level configuration
