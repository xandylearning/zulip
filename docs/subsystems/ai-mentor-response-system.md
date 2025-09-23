# AI Mentor Response System - Event-Driven LangGraph Architecture

## Overview

The AI Mentor Response System is a sophisticated event-driven feature that enables intelligent AI-powered responses in mentor-student communications within Zulip. The system uses LangGraph multi-agent workflows orchestrated through Zulip's event system to analyze mentor communication patterns and generate contextually appropriate responses when mentors are unavailable.

## Key Features

### 1. Event-Driven Multi-Agent Processing
- **LangGraph Orchestration**: Five specialized agents working in coordinated workflows
- **Asynchronous Processing**: AI conversations processed through Zulip's event system for scalability
- **Message Tagging**: Complete metadata tracking with `is_ai_generated` and `ai_metadata` database fields
- **Event Monitoring**: Comprehensive event lifecycle tracking from trigger to completion

### 2. Advanced Style Analysis
- **AI-Powered Pattern Recognition**: Uses LLM analysis for mentor communication patterns
- **Confidence Scoring**: Measures how well the system understands a mentor's style (0.0-1.0)
- **Caching System**: Efficient style profile caching with 24-hour duration
- **Continuous Learning**: Style profiles updated based on new mentor messages

### 3. Intelligent Response Generation
- **Multi-Variant Generation**: Creates multiple response candidates for quality selection
- **Context Integration**: Considers conversation history, urgency, and academic context
- **Quality Scoring**: Each response variant evaluated for authenticity and appropriateness
- **Real-time Suggestions**: Generates contextual suggestions for mentors alongside auto-responses

### 4. Robust Event System
- **Event-Driven Architecture**: All AI processing triggered through `ai_agent_conversation` events
- **Real-time Monitoring**: Tracks all AI mentor interactions through comprehensive event system
- **Analytics Integration**: Complete logging, metrics collection, and performance monitoring
- **Error Recovery**: Robust error detection, recovery mechanisms, and fallback strategies

## Architecture

### Event-Driven LangGraph Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                    Zulip Message Sending Pipeline                     │
├───────────────────────────────────────────────────────────────────────┤
│  Student → Mentor Message → trigger_ai_agent_conversation()           │
│                                       ↓                               │
│                          ai_agent_conversation Event                  │
└───────────────────────────────────────┬───────────────────────────────┘
                                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     Event Listener Processing                        │
├───────────────────────────────────────────────────────────────────────┤
│  handle_ai_agent_conversation() → LangGraph Agent Orchestrator       │
└───────────────────────────────────────┬───────────────────────────────┘
                                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│              LangGraph Multi-Agent Workflow System                   │
├───────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ Style Analysis  │  │ Context      │  │ Response Generation     │   │
│  │     Agent       │  │ Analysis     │  │        Agent            │   │
│  │ • AI Pattern    │  │   Agent      │  │ • Multi-Variant Gen     │   │
│  │   Recognition   │  │ • Urgency    │  │ • Quality Scoring       │   │
│  │ • Confidence    │  │ • Sentiment  │  │ • Style Application     │   │
│  │ • Caching       │  │ • Academic   │  │ • Authenticity Check    │   │
│  └─────────────────┘  └──────────────┘  └─────────────────────────┘   │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ Intelligent     │  │ Decision     │  │ Message Sending &       │   │
│  │ Suggestions     │  │ Making       │  │ Metadata Tagging        │   │
│  │    Agent        │  │   Agent      │  │                         │   │
│  │ • Contextual    │  │ • Threshold  │  │ • is_ai_generated=True  │   │
│  │ • Real-time     │  │ • Quality    │  │ • ai_metadata JSON      │   │
│  │ • Categorized   │  │ • Business   │  │ • triggered_by_event    │   │
│  │ • Prioritized   │  │   Rules      │  │ • Event Notifications   │   │
│  └─────────────────┘  └──────────────┘  └─────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
                                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        Event System Layer                            │
├───────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ Event Analytics │  │ Performance  │  │ Error Handling &        │   │
│  │                 │  │ Monitoring   │  │ Recovery                │   │
│  │ • Usage Metrics │  │ • Response   │  │ • Error Events          │   │
│  │ • Quality Logs  │  │   Times      │  │ • Fallback Logic        │   │
│  │ • User Feedback │  │ • Token Cost │  │ • Notification Alerts   │   │
│  │ • Audit Trails  │  │ • Success    │  │ • Recovery Actions      │   │
│  └─────────────────┘  └──────────────┘  └─────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
```

### Event Flow with Agent Processing

```
Student Message → Message Send Pipeline → AI Agent Event Creation
                                               ↓
                                   ai_agent_conversation Event
                                               ↓
                                    Event Listener Processing
                                               ↓
                              LangGraph Agent Orchestrator
                                     ↓              ↓
                          5 Specialized Agents → Decision Engine
                                               ↓
                                  AI Response Generation
                                               ↓
                         Message Tagged with AI Metadata
                                               ↓
                              Event Notifications Sent
                                     ↓      ↓       ↓
                            Analytics  Monitoring  Audit
```

## Configuration

### Current Production Configuration (v2.0)

The system is configured through environment variables and automatically integrated into Zulip's settings:

```bash
# Core Event-Driven System
USE_LANGGRAPH_AGENTS=true                    # Enable LangGraph agent system
PORTKEY_API_KEY=your_portkey_api_key         # Portkey AI gateway credentials

# AI Model Settings
AI_MENTOR_MODEL=gpt-4                        # LLM model for agent processing
AI_MENTOR_TEMPERATURE=0.7                    # Response creativity level
AI_MENTOR_MAX_TOKENS=1000                    # Maximum response length

# Decision Thresholds (Minutes-Based Configuration)
AI_MENTOR_MIN_ABSENCE_MINUTES=240            # 4 hours before AI responds (240 minutes)
AI_MENTOR_MAX_DAILY_RESPONSES=3              # Maximum daily AI responses per mentor
AI_MENTOR_URGENCY_THRESHOLD=0.7              # Urgency score threshold (0.0-1.0)
AI_MENTOR_CONFIDENCE_THRESHOLD=0.6           # Confidence threshold (0.0-1.0)

# Agent Workflow Configuration
AI_STYLE_MIN_MESSAGES=5                      # Minimum messages for style analysis
AI_STYLE_CACHE_HOURS=24                      # Style profile cache duration
AI_CONTEXT_HISTORY_LIMIT=10                  # Conversation history limit
AI_RESPONSE_VARIANTS=3                       # Number of response candidates

# System Performance
AI_MENTOR_MAX_RETRIES=3                      # Retry attempts for LLM calls
AI_MENTOR_TIMEOUT=30                         # Request timeout (seconds)
AI_AGENT_STATE_DB_PATH=/var/lib/zulip/ai_agent_state.db  # State persistence path
```

**Database Schema Updates:**
```sql
-- Added to Message model via migration 10003_add_ai_message_fields.py
ALTER TABLE zerver_message ADD COLUMN is_ai_generated BOOLEAN DEFAULT FALSE;
ALTER TABLE zerver_message ADD COLUMN ai_metadata JSONB;
CREATE INDEX zerver_message_is_ai_generated_idx ON zerver_message(is_ai_generated);

-- Applied to ArchivedMessage model as well
ALTER TABLE zerver_archivedmessage ADD COLUMN is_ai_generated BOOLEAN DEFAULT FALSE;
ALTER TABLE zerver_archivedmessage ADD COLUMN ai_metadata JSONB;
```

**See:** [Complete Environment Variables Guide](../production/ai-agent-environment-variables.md)

### Realm-Level Permissions

The AI mentor system integrates with Zulip's existing permission system:

- **can_summarize_topics_group**: Users in this group can use AI mentor features
- **Mentors**: Must have ROLE_MENTOR to have their style analyzed
- **Students**: Must have ROLE_STUDENT to receive AI responses

## API Reference

### Endpoints

#### Process Mentor Message Request
```
POST /api/v1/ai_mentor/process_message
```

**Parameters:**
- `recipient_user_id` (int): ID of the mentor
- `message_content` (string): Student's message
- `enable_ai_assistance` (bool, optional): Enable AI responses (default: true)

**Response:**
```json
{
    "message_id": 12345,
    "ai_response_sent": true,
    "ai_response_reason": "auto_response_generated",
    "mentor_notified": true
}
```

#### Get Mentor AI Settings
```
GET /api/v1/ai_mentor/settings
```

**Response:**
```json
{
    "ai_features_enabled": true,
    "auto_response_enabled": true,
    "style_analysis_available": true,
    "daily_response_limit": 3,
    "min_absence_hours": 4,
    "style_confidence": 0.85,
    "dominant_tone": "supportive",
    "teaching_approach": "questioning"
}
```

#### Update Mentor AI Preferences
```
POST /api/v1/ai_mentor/preferences
```

**Parameters:**
- `auto_response_enabled` (bool): Enable/disable auto responses
- `max_daily_responses` (int, optional): Override daily limit
- `min_absence_hours` (int, optional): Override absence threshold

#### Get AI Interaction History
```
GET /api/v1/ai_mentor/history?days_back=7&limit=50
```

**Response:**
```json
{
    "interactions": [
        {
            "timestamp": "2024-01-15T10:30:00Z",
            "type": "auto_response_generated",
            "mentor_id": 123,
            "student_message_preview": "Need help with...",
            "ai_response_preview": "That's a great question...",
            "decision_reason": "mentor_absent_6_hours",
            "urgency_score": 0.8
        }
    ],
    "total_auto_responses": 5,
    "ai_usage_stats": {
        "responses_this_week": 12,
        "avg_response_time": "2.1 seconds",
        "student_satisfaction": 0.85
    }
}
```

## Event System

### Event Types

#### 1. AI Mentor Response Event
Triggered when AI generates a response on behalf of a mentor.

```json
{
    "type": "ai_mentor_response",
    "id": 12345,
    "mentor": {
        "user_id": 123,
        "full_name": "Dr. Smith",
        "email": "smith@university.edu"
    },
    "student": {
        "user_id": 456,
        "full_name": "Alice Johnson",
        "email": "alice@university.edu"
    },
    "original_message_preview": "I'm struggling with calculus...",
    "ai_response_preview": "That's a great question about derivatives...",
    "style_confidence": 0.85,
    "decision_reason": "mentor_absent_5_hours",
    "timestamp": "2024-01-15T10:30:00Z",
    "ai_generated": true,
    "requires_mentor_review": false
}
```

#### 2. Style Analysis Event
Triggered when mentor communication style is analyzed or updated.

```json
{
    "type": "ai_mentor_style_analysis",
    "mentor": {
        "user_id": 123,
        "full_name": "Dr. Smith",
        "email": "smith@university.edu"
    },
    "style_profile": {
        "confidence_score": 0.85,
        "dominant_tone": "supportive",
        "teaching_approach": "questioning",
        "message_count_analyzed": 45,
        "last_updated": "2024-01-15T10:30:00Z"
    },
    "analysis_type": "periodic",
    "timestamp": "2024-01-15T10:30:00Z",
    "recommendations": [
        "Your questioning style promotes critical thinking",
        "Consider balancing resource sharing with direct explanation"
    ]
}
```

#### 3. Settings Change Event
Triggered when AI mentor settings are modified.

```json
{
    "type": "ai_mentor_settings_change",
    "mentor": {
        "user_id": 123,
        "full_name": "Dr. Smith",
        "email": "smith@university.edu"
    },
    "changed_by": {
        "user_id": 123,
        "full_name": "Dr. Smith",
        "email": "smith@university.edu"
    },
    "setting": {
        "name": "auto_response_enabled",
        "old_value": true,
        "new_value": false
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

#### 4. Error Event
Triggered when the AI mentor system encounters errors.

```json
{
    "type": "ai_mentor_error",
    "mentor": {"user_id": 123, "full_name": "Dr. Smith"},
    "student": {"user_id": 456, "full_name": "Alice Johnson"},
    "error": {
        "type": "ai_api_failure",
        "message": "Rate limit exceeded",
        "severity": "medium"
    },
    "context": {"retry_count": 3, "last_success": "2024-01-15T10:00:00Z"},
    "timestamp": "2024-01-15T10:30:00Z",
    "requires_intervention": false
}
```

#### 5. Feedback Event
Triggered when users provide feedback on AI responses.

```json
{
    "type": "ai_mentor_feedback",
    "message_id": 12345,
    "mentor": {"user_id": 123, "full_name": "Dr. Smith"},
    "student": {"user_id": 456, "full_name": "Alice Johnson"},
    "feedback": {
        "type": "rating",
        "score": 4.0,
        "comment": "Very helpful response"
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Event Listeners

Event listeners are automatically registered and handle:

- **Analytics Tracking**: Updates counters and metrics
- **Quality Monitoring**: Flags low-confidence responses for review
- **Error Recovery**: Triggers automatic recovery actions
- **Notifications**: Sends alerts to mentors and administrators
- **Caching**: Updates cached style profiles and settings

## Decision Logic

### Auto-Response Conditions

An AI response is generated only when ALL conditions are met:

1. **Role Verification**: Sender is STUDENT, recipient is MENTOR
2. **Permission Check**: Mentor has AI features enabled
3. **Mentor Absence**: Last response > `min_absence_hours` ago
4. **Daily Limit**: Auto-responses today < `max_daily_responses`
5. **Message Urgency**: Urgency score > `urgency_threshold` (0.7)
6. **Style Confidence**: Mentor style confidence > `min_confidence` (0.6)
7. **Human Request Check**: Student hasn't requested human interaction

### Urgency Assessment

Message urgency is calculated based on:

- **High urgency keywords**: "urgent", "asap", "emergency", "help", "stuck", "deadline"
- **Medium urgency keywords**: "question", "clarify", "understand", "explain"
- **Low urgency keywords**: "thanks", "update", "by the way", "whenever"
- **Conversation context**: Repeated questions increase urgency

### Style Confidence Calculation

Style confidence is based on:

- **Message Count**: Higher confidence with more analyzed messages (target: 50+)
- **Message Diversity**: Different dates, recipients, and vocabulary variety
- **Pattern Consistency**: Stable communication patterns over time

## Monitoring and Analytics

### Key Metrics

#### Response Metrics
- Total AI responses per day/week/month
- Response confidence distribution
- Decision reason breakdown
- Response time averages

#### Quality Metrics
- Student satisfaction scores
- Mentor approval ratings
- Low-confidence response rates
- Error rates by type

#### Usage Metrics
- Active mentors using AI features
- Style analysis completion rates
- Settings change frequency
- Feature adoption rates

### Dashboards

#### Mentor Dashboard
- Personal AI response statistics
- Style analysis results and recommendations
- Recent interactions and feedback
- Settings and preferences

#### Admin Dashboard
- System-wide AI mentor metrics
- Error monitoring and alerts
- Usage analytics and trends
- Quality control reports

## Security and Privacy

### Data Protection
- **Realm Isolation**: AI context never crosses realm boundaries
- **Minimal Data Storage**: Only necessary metadata is cached
- **Anonymized Analytics**: Personal identifiers removed from analytics
- **Consent Management**: Users can opt-out of AI features

### Access Control
- **Role-Based Permissions**: Integrated with Zulip's permission system
- **API Security**: All endpoints require authentication
- **Admin Oversight**: Realm administrators can monitor and disable features

### Transparency
- **AI Indicators**: All AI-generated messages are clearly marked
- **Audit Logging**: Complete trail of AI interactions
- **User Control**: Mentors can review and override AI responses

## Troubleshooting

### Common Issues

#### 1. AI Responses Not Generated
**Symptoms**: No AI responses despite student messages

**Possible Causes:**
- Mentor hasn't been absent long enough
- Daily response limit reached
- Style confidence too low
- Message urgency below threshold

**Solutions:**
- Check mentor's last activity time
- Review daily response count in analytics
- Increase message history for style analysis
- Manually classify message urgency

#### 2. Low Style Confidence
**Symptoms**: Style confidence below 0.6

**Possible Causes:**
- Insufficient message history (< 10 messages)
- Inconsistent communication patterns
- Limited vocabulary diversity

**Solutions:**
- Wait for more message data
- Review message content for patterns
- Manually trigger style reanalysis

#### 3. High Error Rates
**Symptoms**: Frequent AI mentor errors

**Possible Causes:**
- AI API rate limiting
- Network connectivity issues
- Invalid configuration

**Solutions:**
- Check AI API status and limits
- Review network configuration
- Validate settings.py configuration

### Debugging

#### Enable Debug Logging
```python
LOGGING = {
    'loggers': {
        'zerver.lib.ai_mentor_response': {
            'level': 'DEBUG',
        },
        'zerver.actions.ai_mentor_events': {
            'level': 'DEBUG',
        },
        'zerver.event_listeners.ai_mentor': {
            'level': 'DEBUG',
        },
    }
}
```

#### Check Event Processing
```bash
# Monitor AI mentor events in real-time
tail -f /var/log/zulip/events.log | grep ai_mentor

# Check event listener processing
tail -f /var/log/zulip/django.log | grep "AI mentor"
```

#### Verify Configuration
```python
# In Django shell
from django.conf import settings
print(f"AI Mentor Enabled: {getattr(settings, 'AI_MENTOR_ENABLED', False)}")
print(f"AI Model: {getattr(settings, 'AI_MENTOR_MODEL', 'Not set')}")
```

## Development and Testing

### Running Tests
```bash
# Run all AI mentor tests
./tools/test-backend zerver.tests.test_ai_mentor_response

# Run specific test class
./tools/test-backend zerver.tests.test_ai_mentor_response.MentorStyleAnalyzerTest

# Run with verbose output
./tools/test-backend zerver.tests.test_ai_mentor_response --verbose
```

### Development Setup
```bash
# Enable AI mentor features in development
export AI_MENTOR_ENABLED=True
export AI_MENTOR_MODEL=mock  # Use mock AI for testing

# Start development server with AI mentor logging
./tools/run-dev --ai-mentor-debug
```

### Testing Guidelines

#### Unit Tests
- Test all decision logic conditions
- Verify style analysis algorithms
- Check error handling paths
- Validate event generation

#### Integration Tests
- Test complete message processing flow
- Verify event system integration
- Check API endpoint functionality
- Test permission enforcement

#### Performance Tests
- Measure response generation time
- Test under high message volume
- Verify caching effectiveness
- Check memory usage patterns

## Roadmap

### Phase 1: Core Features (Completed)
- ✅ Mentor style analysis
- ✅ Selective auto-response
- ✅ Event system integration
- ✅ Basic API endpoints

### Phase 2: Enhanced Intelligence (In Progress)
- 🔄 Advanced natural language processing
- 🔄 Multi-modal style analysis
- 🔄 Sentiment-aware responses
- 🔄 Conversation context memory

### Phase 3: Integration Expansion (Planned)
- 📋 LMS data integration
- 📋 Advanced analytics dashboard
- 📋 Mobile app support
- 📋 Third-party AI model support

### Phase 4: Advanced Features (Future)
- 🔮 Predictive response suggestions
- 🔮 Cross-mentor style learning
- 🔮 Adaptive confidence thresholds
- 🔮 Real-time collaboration hints

## Support and Feedback

### Getting Help
- **Documentation**: Complete feature documentation in `/docs/subsystems/`
- **Issue Tracking**: Report bugs and feature requests on GitHub
- **Community**: Join discussions in the Zulip development community

### Contributing
- **Code Contributions**: Follow Zulip's contribution guidelines
- **Testing**: Help expand test coverage
- **Documentation**: Improve and update documentation
- **Feedback**: Share usage experiences and suggestions

### Contact
For questions or support regarding the AI Mentor Response System:
- **GitHub Issues**: [zulip/zulip](https://github.com/zulip/zulip/issues)
- **Development Discussion**: Zulip development community
- **Security Issues**: security@zulip.com

---

*This documentation covers the AI Mentor Response System as implemented in Zulip. For the most up-to-date information, refer to the source code and recent commit history.*