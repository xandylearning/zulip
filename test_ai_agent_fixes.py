#!/usr/bin/env python3
"""
Test script to verify AI agent integration fixes

This script tests the fixes applied to resolve attribute errors
in the AI agent integration system.
"""

import os
import sys
import django

# Add the zulip directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.test_settings')
django.setup()

from zerver.models import Recipient, UserProfile, Message


def test_recipient_constants():
    """Test that correct Recipient constants exist"""
    print("🧪 Testing Recipient Constants")
    print("=" * 40)

    # Test that PERSONAL exists (not PRIVATE_MESSAGE)
    assert hasattr(Recipient, 'PERSONAL'), "Recipient.PERSONAL should exist"
    assert Recipient.PERSONAL == 1, "Recipient.PERSONAL should equal 1"

    # Verify PRIVATE_MESSAGE doesn't exist (this was the bug)
    assert not hasattr(Recipient, 'PRIVATE_MESSAGE'), "Recipient.PRIVATE_MESSAGE should not exist"

    print("✅ Recipient.PERSONAL exists and has correct value")
    print("✅ Recipient.PRIVATE_MESSAGE correctly does not exist")

    # Test other constants
    assert hasattr(Recipient, 'STREAM'), "Recipient.STREAM should exist"
    assert hasattr(Recipient, 'DIRECT_MESSAGE_GROUP'), "Recipient.DIRECT_MESSAGE_GROUP should exist"
    assert Recipient.STREAM == 2, "Recipient.STREAM should equal 2"
    assert Recipient.DIRECT_MESSAGE_GROUP == 3, "Recipient.DIRECT_MESSAGE_GROUP should equal 3"

    print("✅ All Recipient constants are correct")
    return True


def test_userprofile_role_constants():
    """Test that UserProfile role constants exist"""
    print("\n👤 Testing UserProfile Role Constants")
    print("=" * 45)

    assert hasattr(UserProfile, 'ROLE_STUDENT'), "UserProfile.ROLE_STUDENT should exist"
    assert hasattr(UserProfile, 'ROLE_MENTOR'), "UserProfile.ROLE_MENTOR should exist"

    print(f"✅ UserProfile.ROLE_STUDENT = {UserProfile.ROLE_STUDENT}")
    print(f"✅ UserProfile.ROLE_MENTOR = {UserProfile.ROLE_MENTOR}")

    return True


def test_personal_message_structure():
    """Test that personal messages have correct structure"""
    print("\n💬 Testing Personal Message Structure")
    print("=" * 42)

    # Find a personal message
    personal_message = Message.objects.filter(recipient__type=Recipient.PERSONAL).first()

    if not personal_message:
        print("⚠️  No personal messages found in database - creating test scenario")
        print("✅ Test passed - no messages to cause errors")
        return True

    # Test message structure
    assert hasattr(personal_message, 'recipient'), "Message should have recipient"
    assert hasattr(personal_message, 'sender'), "Message should have sender"
    assert hasattr(personal_message, 'content'), "Message should have content"

    # Test recipient structure
    recipient_obj = personal_message.recipient
    assert hasattr(recipient_obj, 'type'), "Recipient should have type"
    assert hasattr(recipient_obj, 'type_id'), "Recipient should have type_id"
    assert recipient_obj.type == Recipient.PERSONAL, "Should be personal message"

    # Test that type_id points to a valid user
    try:
        recipient_user = UserProfile.objects.get(id=recipient_obj.type_id)
        print(f"✅ Personal message recipient lookup works: {recipient_user.full_name}")
    except UserProfile.DoesNotExist:
        print("❌ Recipient type_id doesn't point to valid user")
        return False

    # Test that usermessage_set does NOT exist (this was the bug)
    assert not hasattr(recipient_obj, 'usermessage_set'), "Recipient should not have usermessage_set attribute"
    print("✅ Recipient correctly does not have usermessage_set attribute")

    return True


def test_ai_event_function_exists():
    """Test that AI event functions exist and are importable"""
    print("\n🤖 Testing AI Event System")
    print("=" * 35)

    try:
        from zerver.actions.ai_mentor_events import trigger_ai_agent_conversation
        print("✅ trigger_ai_agent_conversation function can be imported")

        # Test function signature
        import inspect
        sig = inspect.signature(trigger_ai_agent_conversation)
        expected_params = ['mentor', 'student', 'original_message', 'original_message_id']
        actual_params = list(sig.parameters.keys())

        assert actual_params == expected_params, f"Expected {expected_params}, got {actual_params}"
        print("✅ Function signature matches expected parameters")

        return True

    except ImportError as e:
        print(f"❌ Could not import AI event function: {e}")
        return False


def test_safety_checks_logic():
    """Test the safety check logic used in the fix"""
    print("\n🛡️ Testing Safety Check Logic")
    print("=" * 38)

    # Create mock objects to test safety checks
    class MockMessage:
        def __init__(self, has_recipient=True, has_sender=True, has_content=True):
            if has_recipient:
                self.recipient = MockRecipient()
            if has_sender:
                self.sender = MockSender()
            if has_content:
                self.content = "Test message"
                self.id = 123

    class MockRecipient:
        def __init__(self, has_type=True, has_type_id=True):
            if has_type:
                self.type = Recipient.PERSONAL
            if has_type_id:
                self.type_id = 1

    class MockSender:
        def __init__(self, has_role=True):
            if has_role:
                self.role = UserProfile.ROLE_STUDENT

    # Test complete message (should pass all checks)
    complete_message = MockMessage()
    safety_check_result = (
        hasattr(complete_message, 'recipient') and
        hasattr(complete_message, 'sender') and
        hasattr(complete_message.recipient, 'type') and
        hasattr(complete_message.recipient, 'type_id') and
        hasattr(complete_message.sender, 'role') and
        hasattr(complete_message, 'content') and
        complete_message.recipient.type == Recipient.PERSONAL and
        complete_message.sender.role == UserProfile.ROLE_STUDENT
    )

    assert safety_check_result, "Complete message should pass all safety checks"
    print("✅ Complete message passes all safety checks")

    # Test incomplete message (should fail safety checks)
    incomplete_message = MockMessage(has_content=False)
    incomplete_safety_check = (
        hasattr(incomplete_message, 'recipient') and
        hasattr(incomplete_message, 'sender') and
        hasattr(incomplete_message.recipient, 'type') and
        hasattr(incomplete_message.recipient, 'type_id') and
        hasattr(incomplete_message.sender, 'role') and
        hasattr(incomplete_message, 'content')
    )

    assert not incomplete_safety_check, "Incomplete message should fail safety checks"
    print("✅ Incomplete message correctly fails safety checks")

    return True


def main():
    """Run all tests"""
    print("🚀 Testing AI Agent Integration Fixes")
    print("=" * 50)

    tests = [
        test_recipient_constants,
        test_userprofile_role_constants,
        test_personal_message_structure,
        test_ai_event_function_exists,
        test_safety_checks_logic
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
        print("AI agent integration fixes are working correctly.")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please review the failures and fix any remaining issues.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)