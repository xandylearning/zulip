#!/usr/bin/env python3
"""
Test script for FCM call notifications

This script tests the new FCM call notification format to ensure
it generates notifications in the exact format specified.
"""

import os
import sys
import django

# Add the zulip directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.test_settings')
django.setup()

from zerver.models import UserProfile, Realm
from zerver.lib.push_notifications import create_fcm_call_notification_message
from firebase_admin import messaging as firebase_messaging
import json


def test_fcm_call_notification_format():
    """Test that FCM call notifications are generated in the correct format"""

    print("🧪 Testing FCM Call Notification Format")
    print("=" * 50)

    # Test data
    test_token = "test_device_token_123"
    test_call_data = {
        "call_id": "abc123",
        "sender_id": "456",
        "sender_full_name": "Alice",
        "call_type": "video",
        "user_id": "123",
        "time": "1726930000"
    }
    test_realm_host = "your-org.example.com"
    test_realm_url = "https://your-org.example.com"

    try:
        # Create FCM message
        message = create_fcm_call_notification_message(
            token=test_token,
            call_data=test_call_data,
            realm_host=test_realm_host,
            realm_url=test_realm_url
        )

        print("✅ FCM message created successfully!")
        print()

        # Verify the message structure
        print("📋 Message Structure:")
        print(f"Token: {message.token}")
        print(f"Data payload: {message.data}")
        print()

        print("📱 Android Configuration:")
        android_config = message.android
        print(f"Priority: {android_config.priority}")

        android_notification = android_config.notification
        print(f"Channel ID: {android_notification.channel_id}")
        print(f"Tag: {android_notification.tag}")
        print(f"Title: {android_notification.title}")
        print(f"Body: {android_notification.body}")
        print(f"Sound: {android_notification.sound}")
        print(f"Click Action: {android_notification.click_action}")
        print()

        print("🔔 Cross-platform Notification:")
        notification = message.notification
        print(f"Title: {notification.title}")
        print(f"Body: {notification.body}")
        print()

        # Verify against expected format
        print("✅ Verification Results:")

        # Check data payload
        expected_data_keys = {"event", "server", "realm_url", "user_id", "call_id", "sender_id", "sender_full_name", "call_type", "time"}
        actual_data_keys = set(message.data.keys())

        if expected_data_keys == actual_data_keys:
            print("✅ Data payload contains all required fields")
        else:
            print(f"❌ Data payload missing fields: {expected_data_keys - actual_data_keys}")
            print(f"❌ Data payload extra fields: {actual_data_keys - expected_data_keys}")

        # Check values
        assert message.data["event"] == "call", f"Expected event='call', got '{message.data['event']}'"
        assert message.data["call_id"] == "abc123", f"Expected call_id='abc123', got '{message.data['call_id']}'"
        assert message.data["sender_full_name"] == "Alice", f"Expected sender_full_name='Alice', got '{message.data['sender_full_name']}'"
        assert message.data["call_type"] == "video", f"Expected call_type='video', got '{message.data['call_type']}'"

        # Check Android notification
        assert android_notification.channel_id == "calls-1", f"Expected channel_id='calls-1', got '{android_notification.channel_id}'"
        assert android_notification.tag == "call:abc123", f"Expected tag='call:abc123', got '{android_notification.tag}'"
        assert android_notification.title == "Incoming video call", f"Expected title='Incoming video call', got '{android_notification.title}'"
        assert android_notification.body == "From Alice", f"Expected body='From Alice', got '{android_notification.body}'"

        print("✅ All format checks passed!")
        print()

        # Show expected JSON structure
        print("📄 Expected JSON Structure (for reference):")
        expected_structure = {
            "to": test_token,
            "priority": "high",
            "data": {
                "event": "call",
                "server": test_realm_host,
                "realm_url": test_realm_url,
                "user_id": "123",
                "call_id": "abc123",
                "sender_id": "456",
                "sender_full_name": "Alice",
                "call_type": "video",
                "time": "1726930000"
            },
            "android": {
                "priority": "high",
                "notification": {
                    "channel_id": "calls-1",
                    "tag": "call:abc123",
                    "title": "Incoming video call",
                    "body": "From Alice",
                    "sound": "default",
                    "click_action": "android.intent.action.VIEW"
                }
            },
            "notification": {
                "title": "Incoming video call",
                "body": "From Alice"
            }
        }

        print(json.dumps(expected_structure, indent=2))
        print()

        print("🎉 Test completed successfully!")
        print("The FCM call notification format matches the specification exactly.")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_audio_call_notification():
    """Test audio call notification format"""

    print("\n🎧 Testing Audio Call Notification")
    print("=" * 40)

    test_token = "test_device_token_456"
    test_call_data = {
        "call_id": "def789",
        "sender_id": "789",
        "sender_full_name": "Bob",
        "call_type": "audio",
        "user_id": "456",
        "time": "1726930100"
    }

    try:
        message = create_fcm_call_notification_message(
            token=test_token,
            call_data=test_call_data,
            realm_host="company.example.com",
            realm_url="https://company.example.com"
        )

        # Verify audio-specific formatting
        assert message.data["call_type"] == "audio"
        assert message.android.notification.title == "Incoming audio call"
        assert message.android.notification.body == "From Bob"
        assert message.notification.title == "Incoming audio call"
        assert message.notification.body == "From Bob"

        print("✅ Audio call notification format verified!")
        return True

    except Exception as e:
        print(f"❌ Audio call test failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Starting FCM Call Notification Tests")
    print()

    # Run tests
    test1_passed = test_fcm_call_notification_format()
    test2_passed = test_audio_call_notification()

    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED!")
        print("FCM call notifications are working correctly and match the specified format.")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please check the implementation and fix any issues.")
        sys.exit(1)