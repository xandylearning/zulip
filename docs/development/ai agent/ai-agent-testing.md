# AI Agent Testing Guide

This document describes the comprehensive testing framework for the AI Agent system in Zulip.

## Test Structure

The AI agent tests are organized into three main test modules located in `/zerver/tests/`:

### 1. `test_ai_agent_integration.py`
Tests the integration between the AI agent system and Zulip's core functionality.

**Test Coverage:**
- Settings configuration and validation
- Message pipeline integration with AI triggers
- AI message tagging and metadata storage
- Event listener integration
- Environment variable configuration
- Complete integration flow testing

**Key Tests:**
```python
def test_settings_configuration()      # AI agent settings loading
def test_message_pipeline_integration() # Student-to-mentor message triggers
def test_ai_message_tagging_fields()   # Database schema for AI messages
def test_event_listener_integration()  # Event system integration
def test_complete_integration_flow()   # End-to-end workflow
```

### 2. `test_ai_event_system.py`
Tests the event-driven architecture that powers the AI agent conversation system.

**Test Coverage:**
- Event system component integration
- Event-driven message processing
- AI metadata tagging with events
- Event flow completeness
- Configuration compatibility
- Event monitoring and analytics

**Key Tests:**
```python
def test_event_system_integration()           # Component imports and setup
def test_message_integration_uses_events()    # Event-based processing
def test_ai_agent_conversation_event_dispatch() # Event dispatch mechanism
def test_ai_message_created_event()           # Monitoring events
def test_complete_event_lifecycle()           # Full event workflow
```

### 3. `test_ai_agent_core.py`
Tests the LangGraph multi-agent core functionality.

**Test Coverage:**
- AI agent orchestrator functionality
- Individual agent components (5 specialized agents)
- Agent workflow state management
- LLM client integration
- Error handling and fallbacks
- Performance monitoring

**Key Tests:**
```python
def test_ai_agent_orchestrator_import()    # Core system imports
def test_individual_agents_exist()         # 5 agent components
def test_style_analysis_agent()            # Style analysis functionality
def test_context_analysis_agent()          # Context assessment
def test_response_generation_agent()       # Response variants
def test_agent_orchestrator_workflow()     # Complete workflow
```

## Test Execution

### Using the AI Test Runner

A specialized test runner is provided at `/tools/test-ai-agents`:

```bash
# Run all AI tests
vagrant ssh -c "cd /srv/zulip && ./tools/test-ai-agents"

# Run specific test module
vagrant ssh -c "cd /srv/zulip && ./tools/test-ai-agents --module integration"
vagrant ssh -c "cd /srv/zulip && ./tools/test-ai-agents --module event_system"
vagrant ssh -c "cd /srv/zulip && ./tools/test-ai-agents --module core"

# Run integration check only
vagrant ssh -c "cd /srv/zulip && ./tools/test-ai-agents --integration-check"

# Verbose output
vagrant ssh -c "cd /srv/zulip && ./tools/test-ai-agents --verbose"
```

### Using Standard Zulip Test Commands

```bash
# Run all AI agent integration tests
vagrant ssh -c "cd /srv/zulip && ./tools/test-backend zerver.tests.test_ai_agent_integration"

# Run specific test
vagrant ssh -c "cd /srv/zulip && ./tools/test-backend zerver.tests.test_ai_agent_integration.AIAgentIntegrationTest.test_settings_configuration"

# Run event system tests
vagrant ssh -c "cd /srv/zulip && ./tools/test-backend zerver.tests.test_ai_event_system"

# Run core agent tests
vagrant ssh -c "cd /srv/zulip && ./tools/test-backend zerver.tests.test_ai_agent_core"
```

## Test Configuration

### Environment Variables for Testing

```bash
# Basic test configuration
export USE_LANGGRAPH_AGENTS=true
export AI_MENTOR_MIN_ABSENCE_MINUTES=5     # Short for testing
export AI_MENTOR_MAX_DAILY_RESPONSES=10    # Higher for testing
export AI_MENTOR_CONFIDENCE_THRESHOLD=0.3  # Lower for testing
export AI_MENTOR_URGENCY_THRESHOLD=0.3     # Lower for testing

# Mock API keys for testing (optional)
export PORTKEY_API_KEY=test_key
export PORTKEY_VIRTUAL_KEY=test_virtual_key
```

### Django Settings Override

Tests use Django's `@override_settings` decorator to control configuration:

```python
@override_settings(
    USE_LANGGRAPH_AGENTS=True,
    AI_MENTOR_MIN_ABSENCE_MINUTES=5,
    AI_MENTOR_MAX_DAILY_RESPONSES=3,
)
def test_example(self):
    # Test with overridden settings
    pass
```

## Test Data and Fixtures

### User Roles
Tests create users with appropriate roles:
```python
self.mentor = self.example_user("hamlet")
self.mentor.role = UserProfile.ROLE_MENTOR
self.mentor.save()

self.student = self.example_user("othello")
self.student.role = UserProfile.ROLE_STUDENT
self.student.save()
```

### Mock AI Responses
```python
@patch('zerver.lib.ai_mentor_response.handle_potential_ai_response')
def test_ai_workflow(self, mock_ai_response):
    mock_ai_response.return_value = MagicMock(
        content="AI generated response",
        confidence=0.85,
        model='gpt-4'
    )
    # Test AI workflow
```

## Test Dependencies

### Required for Basic Tests
- Django test framework
- Mock and patch functionality
- Zulip test infrastructure

### Required for Full Agent Tests
- LangGraph (optional - tests skip if not available)
- Portkey AI client (mocked in tests)
- SQLite for state persistence

### Optional Dependencies
- Redis (for caching tests)
- External API mocking

## Expected Test Outcomes

### Integration Check Results
```
🔍 Running AI Integration Check
----------------------------------------
✅ AI agent settings importable
✅ AI mentor events importable
✅ AI event listeners importable
⚠️  AI agent core not importable: No module named 'langgraph'
   (This is expected if LangGraph dependencies are not installed)

✅ Integration Check Passed!
```

### Full Test Suite Results
```
🚀 Running AI Agent Test Suite
==================================================
[1/3] Testing test_ai_agent_integration
✅ test_ai_agent_integration PASSED

[2/3] Testing test_ai_event_system
✅ test_ai_event_system PASSED

[3/3] Testing test_ai_agent_core
✅ test_ai_agent_core PASSED

==================================================
🎯 AI Agent Test Results
==================================================
✅ All Tests Passed: 3/3

🎉 AI Agent System Tests Complete!
```

## Troubleshooting

### Common Issues

1. **Django Settings Not Configured**
   ```
   Error: settings are not configured
   ```
   Solution: Ensure DJANGO_SETTINGS_MODULE is set or run via test-backend

2. **Import Errors for LangGraph**
   ```
   ModuleNotFoundError: No module named 'langgraph'
   ```
   Solution: This is expected - tests will skip or mock LangGraph functionality

3. **Database Migration Issues**
   ```
   Error: no such column: zerver_message.is_ai_generated
   ```
   Solution: Run migrations: `python manage.py migrate`

### Test Environment Setup

1. **Ensure test database is clean:**
   ```bash
   vagrant ssh -c "cd /srv/zulip && ./tools/test-backend --rerun"
   ```

2. **Verify AI agent migration applied:**
   ```bash
   vagrant ssh -c "cd /srv/zulip && python manage.py showmigrations zerver | grep add_ai_message_fields"
   ```

3. **Check event listener registration:**
   ```bash
   vagrant ssh -c "cd /srv/zulip && python -c 'import django; django.setup(); from zerver.event_listeners.ai_mentor import ai_mentor_event_listener; print(\"Event listener loaded successfully\")'"
   ```

## Continuous Integration

### Adding to CI Pipeline

To include AI agent tests in your CI pipeline:

```yaml
# In your CI configuration
- name: Run AI Agent Tests
  run: |
    vagrant ssh -c "cd /srv/zulip && ./tools/test-ai-agents"
```

### Test Performance

- Integration tests: ~5-10 seconds per test
- Event system tests: ~3-5 seconds per test
- Core agent tests: ~2-3 seconds per test (with mocking)
- Full test suite: ~30-60 seconds

## Related Documentation

- [AI Messaging Integration](../subsystems/ai-messaging-integration.md)
- [AI Mentor Response System](../subsystems/ai-mentor-response-system.md)
- [AI Agent Environment Variables](../production/ai-agent-environment-variables.md)
- [Zulip Testing Guide](../testing/testing.md)