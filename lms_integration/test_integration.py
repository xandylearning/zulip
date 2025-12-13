#!/usr/bin/env python3
"""
Simple integration test for TestPress JWT authentication system.

This script tests the basic functionality of our JWT authentication
implementation without requiring a full Django environment.
"""

import sys
import os
import json
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_jwt_token_validation():
    """Test JWT token validation logic."""
    print("Testing JWT token validation...")

    # Import our security validator
    try:
        from lms_integration.security import SecurityValidator
        validator = SecurityValidator()

        # Test valid JWT format
        valid_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxMjN9.abc123def456"
        is_valid, error = validator.validate_jwt_token(valid_token)
        assert is_valid, f"Valid token should pass: {error}"
        print("✓ Valid JWT token format accepted")

        # Test invalid formats
        invalid_tokens = [
            "",  # Empty
            "invalid",  # Not JWT format
            "a.b",  # Missing part
            "<script>alert('xss')</script>",  # XSS attempt
            "a" * 10000,  # Too long
        ]

        for token in invalid_tokens:
            is_valid, error = validator.validate_jwt_token(token)
            assert not is_valid, f"Invalid token should fail: {token[:50]}"

        print("✓ Invalid JWT tokens correctly rejected")

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

    return True

def test_security_patterns():
    """Test security pattern detection."""
    print("\nTesting security pattern detection...")

    try:
        from lms_integration.security import SecurityValidator
        validator = SecurityValidator()

        # Test clean data
        clean_data = {"token": "valid.jwt.token", "user": "test@example.com"}
        is_valid, error = validator.validate_request_data(clean_data)
        assert is_valid, f"Clean data should pass: {error}"
        print("✓ Clean request data accepted")

        # Test suspicious patterns
        suspicious_data = [
            {"token": "<script>alert('xss')</script>"},
            {"user": "'; DROP TABLE users; --"},
            {"path": "../../../etc/passwd"},
        ]

        for data in suspicious_data:
            is_valid, error = validator.validate_request_data(data)
            assert not is_valid, f"Suspicious data should fail: {data}"

        print("✓ Suspicious patterns correctly detected")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

    return True

def test_file_structure():
    """Test that all required files exist and are properly structured."""
    print("\nTesting file structure...")

    required_files = [
        'lms_integration/auth_backend.py',
        'lms_integration/jwt_validator.py',
        'lms_integration/user_sync.py',
        'lms_integration/security.py',
        'lms_integration/views.py',
        'lms_integration/urls.py',
    ]

    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"✗ Missing file: {file_path}")
            return False

        # Basic syntax check
        with open(file_path, 'r') as f:
            content = f.read()
            if not content.strip():
                print(f"✗ Empty file: {file_path}")
                return False

    print("✓ All required files exist and have content")
    return True

def test_url_patterns():
    """Test URL pattern configuration."""
    print("\nTesting URL patterns...")

    try:
        with open('lms_integration/urls.py', 'r') as f:
            content = f.read()

        # Check for our JWT endpoints
        required_patterns = [
            'testpress_jwt_auth',
            'testpress_jwt_login',
            'auth/jwt/',
            'auth/jwt/login/',
        ]

        for pattern in required_patterns:
            if pattern not in content:
                print(f"✗ Missing URL pattern: {pattern}")
                return False

        print("✓ JWT authentication URL patterns configured")

    except Exception as e:
        print(f"✗ URL test failed: {e}")
        return False

    return True

def test_settings_integration():
    """Test settings integration."""
    print("\nTesting settings integration...")

    try:
        with open('zproject/computed_settings.py', 'r') as f:
            content = f.read()

        # Check for our settings
        required_settings = [
            'TESTPRESS_API_BASE_URL',
            'TESTPRESS_JWT_ENABLED',
            'lms_integration.auth_backend.TestPressJWTAuthBackend',
        ]

        for setting in required_settings:
            if setting not in content:
                print(f"✗ Missing setting: {setting}")
                return False

        print("✓ TestPress settings properly configured")

    except Exception as e:
        print(f"✗ Settings test failed: {e}")
        return False

    return True

def main():
    """Run all tests."""
    print("TestPress JWT Authentication Integration Test")
    print("=" * 50)

    tests = [
        test_file_structure,
        test_jwt_token_validation,
        test_security_patterns,
        test_url_patterns,
        test_settings_integration,
    ]

    passed = 0
    total = len(tests)

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"✗ {test_func.__name__} failed")
        except Exception as e:
            print(f"✗ {test_func.__name__} error: {e}")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Integration is ready for deployment.")
        print("\nNext steps:")
        print("1. Configure TestPress API base URL in settings")
        print("2. Test with actual TestPress JWT tokens")
        print("3. Verify user creation and synchronization")
        print("4. Set up monitoring and logging")
        return True
    else:
        print("❌ Some tests failed. Please fix issues before deploying.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)