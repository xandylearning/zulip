#!/usr/bin/env python3
"""
Test script to verify AI event listeners are properly registered and working
"""

import os
import sys
import django

# Add the zulip directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.test_settings')
django.setup()


def test_event_listener_imports():
    """Test that AI event listener modules can be imported"""
    print("🧪 Testing AI Event Listener Imports")
    print("=" * 45)

    try:
        from zerver.event_listeners.ai_mentor import handle_ai_agent_conversation
        print("✅ ai_mentor.handle_ai_agent_conversation imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import ai_mentor.handle_ai_agent_conversation: {e}")
        return False

    try:
        from zerver.event_listeners.ai_message_monitor import handle_ai_message_created, handle_ai_agent_performance
        print("✅ ai_message_monitor functions imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import ai_message_monitor functions: {e}")
        return False

    return True


def test_event_listener_registration():
    """Test that AI event listeners are properly registered"""
    print("\n🔧 Testing Event Listener Registration")
    print("=" * 45)

    try:
        from zerver.event_listeners.registry import event_listener_registry

        # Force registration by importing the modules
        from zerver.event_listeners import ai_mentor, ai_message_monitor

        listeners = event_listener_registry.list_listeners()
        print(f"📋 Registered listeners: {listeners}")

        # Check if our AI listeners are registered
        ai_mentor_registered = 'ai_mentor' in listeners or 'AIMentorEventHandler' in listeners
        ai_monitor_registered = 'ai_message_monitor' in listeners or 'AIMessageMonitorEventHandler' in listeners

        if ai_mentor_registered:
            print("✅ AI Mentor event handler is registered")
        else:
            print("❌ AI Mentor event handler is NOT registered")

        if ai_monitor_registered:
            print("✅ AI Message Monitor event handler is registered")
        else:
            print("❌ AI Message Monitor event handler is NOT registered")

        return ai_mentor_registered and ai_monitor_registered

    except Exception as e:
        print(f"❌ Error testing event listener registration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ai_event_processing():
    """Test that AI event processing works"""
    print("\n🤖 Testing AI Event Processing")
    print("=" * 35)

    try:
        from zerver.event_listeners.ai_mentor import handle_ai_agent_conversation

        # Create a test event
        test_event = {
            "type": "ai_agent_conversation",
            "mentor": {"id": 1, "full_name": "Test Mentor", "email": "mentor@test.com"},
            "student": {"id": 2, "full_name": "Test Student", "email": "student@test.com"},
            "original_message": "Test message for AI processing",
            "original_message_id": 123,
            "timestamp": "2025-09-23T10:00:00Z"
        }

        # Test the handler (should return True even if AI system is disabled)
        result = handle_ai_agent_conversation(test_event)

        if result:
            print("✅ AI event processing completed successfully")
            return True
        else:
            print("❌ AI event processing failed")
            return False

    except Exception as e:
        print(f"❌ Error testing AI event processing: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ai_settings():
    """Test that AI agent settings are properly configured"""
    print("\n⚙️ Testing AI Agent Settings")
    print("=" * 35)

    try:
        from django.conf import settings

        # Check if AI agent settings are available
        use_ai_agents = getattr(settings, 'USE_LANGGRAPH_AGENTS', None)
        event_listeners_enabled = getattr(settings, 'EVENT_LISTENERS_ENABLED', None)

        print(f"📝 USE_LANGGRAPH_AGENTS: {use_ai_agents}")
        print(f"📝 EVENT_LISTENERS_ENABLED: {event_listeners_enabled}")

        if event_listeners_enabled:
            print("✅ Event listeners are enabled")
        else:
            print("⚠️  Event listeners are disabled")

        if use_ai_agents is not None:
            print("✅ AI agent settings are configured")
        else:
            print("⚠️  AI agent settings not found")

        return event_listeners_enabled is not False  # Allow None or True

    except Exception as e:
        print(f"❌ Error checking AI settings: {e}")
        return False


def test_ai_mentor_events_integration():
    """Test that ai_mentor_events can import the event listeners"""
    print("\n🔗 Testing AI Mentor Events Integration")
    print("=" * 45)

    try:
        # Test the specific import that was failing
        from zerver.actions.ai_mentor_events import trigger_ai_agent_conversation
        print("✅ trigger_ai_agent_conversation imported successfully")

        # Test if the function can be called (it should work even if AI is disabled)
        from zerver.models import UserProfile

        # We won't actually call it since we need real user objects,
        # but the import should work
        print("✅ ai_mentor_events integration working")
        return True

    except ImportError as e:
        print(f"❌ Import error in ai_mentor_events: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing ai_mentor_events integration: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Testing AI Event Listeners Integration")
    print("=" * 50)

    tests = [
        test_event_listener_imports,
        test_event_listener_registration,
        test_ai_settings,
        test_ai_event_processing,
        test_ai_mentor_events_integration
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
        print("AI event listeners are working correctly.")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please review the failures above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)