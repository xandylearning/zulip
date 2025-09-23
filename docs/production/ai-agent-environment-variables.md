# AI Agent Environment Variables Configuration

This document outlines all environment variables required for the LangGraph-based AI agent system with Portkey integration in Zulip.

## Core AI Agent Settings

### Essential Configuration

```bash
# Enable the AI agent system
USE_LANGGRAPH_AGENTS=true

# Portkey AI Gateway Configuration
PORTKEY_API_KEY=your_portkey_api_key_here
PORTKEY_BASE_URL=https://api.portkey.ai/v1
```

### AI Model Configuration

```bash
# LLM Model Settings
AI_MENTOR_MODEL=gpt-4                    # AI model to use (gpt-4, gpt-3.5-turbo, etc.)
AI_MENTOR_TEMPERATURE=0.7               # Response creativity (0.0-1.0)
AI_MENTOR_MAX_TOKENS=1000               # Maximum response length

# System Performance
AI_MENTOR_MAX_RETRIES=3                 # Number of retry attempts on failure
AI_MENTOR_TIMEOUT=30                    # Request timeout in seconds
```

### Decision Thresholds

```bash
# Time-based Settings (in minutes)
AI_MENTOR_MIN_ABSENCE_MINUTES=240       # Minimum mentor absence before AI responds (4 hours)
AI_MENTOR_MAX_DAILY_RESPONSES=3         # Maximum AI responses per mentor per day

# Quality Thresholds (0.0-1.0)
AI_MENTOR_URGENCY_THRESHOLD=0.7         # Minimum urgency score to trigger response
AI_MENTOR_CONFIDENCE_THRESHOLD=0.6      # Minimum confidence score to send response
```

### Data Storage

```bash
# State Persistence
AI_AGENT_STATE_DB_PATH=/var/lib/zulip/ai_agent_state.db
```

## Advanced Configuration

### Workflow Tuning

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

### Feature Flags

```bash
# Enable/Disable Features
AI_ENABLE_STYLE_ANALYSIS=true
AI_ENABLE_CONTEXT_ANALYSIS=true
AI_ENABLE_RESPONSE_GEN=true
AI_ENABLE_SUGGESTIONS=true
AI_ENABLE_AUTO_RESPONSES=true
```

### Logging and Monitoring

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

### Security and Privacy

```bash
# Privacy Settings
AI_REQUIRE_CONSENT=true                # Require explicit user consent
AI_ANONYMIZE_LOGS=true                 # Anonymize logs for privacy
AI_MAX_CONTEXT_DAYS=30                 # Maximum days to retain context data

# Performance Monitoring
AI_ERROR_RATE_THRESHOLD=0.1            # Alert threshold for error rates
```

## Production Deployment

### `/etc/zulip/zulip-secrets.conf`

Add the following to your Zulip secrets configuration:

```ini
# Portkey API credentials
portkey_api_key = your_actual_portkey_api_key_here
portkey_virtual_key = your_actual_portkey_virtual_key_here

# Optional: Additional AI service keys
openai_api_key = your_openai_api_key_if_needed
```

### `/etc/zulip/settings.py` (Production Settings)

```python
# AI Agent System
USE_LANGGRAPH_AGENTS = True

# Import Portkey credentials from secrets
PORTKEY_API_KEY = get_secret("portkey_api_key")

# Production-optimized settings
AI_MENTOR_MIN_ABSENCE_MINUTES = 240  # 4 hours
AI_MENTOR_MAX_DAILY_RESPONSES = 3
AI_MENTOR_CONFIDENCE_THRESHOLD = 0.7  # Higher threshold for production
AI_MENTOR_URGENCY_THRESHOLD = 0.8     # Higher threshold for production

# Production data paths
AI_AGENT_STATE_DB_PATH = "/var/lib/zulip/ai_agent_state.db"

# Enable monitoring
AI_MENTOR_ANALYTICS_ENABLED = True
AI_LOG_INTERACTIONS = True
AI_LOG_DECISIONS = True
```

## Development Settings

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

## Related Documentation

- [AI Messaging Integration](../subsystems/ai-messaging-integration.md)
- [AI Mentor Response System](../subsystems/ai-mentor-response-system.md)
- [Production Settings](../production/settings.md)
- [Security Model](../production/security-model.md)