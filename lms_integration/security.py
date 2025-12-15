"""
Security utilities for TestPress LMS integration.

This module provides security enhancements including input validation,
security logging, and threat detection for JWT authentication endpoints.
"""

import logging
import re
from typing import Optional, Dict, Any
from django.http import HttpRequest
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Security validation and threat detection for TestPress integration."""

    # JWT token pattern validation
    JWT_TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+$')

    # Maximum allowed token length (reasonable JWT size limit)
    MAX_TOKEN_LENGTH = 8192

    # Suspicious request patterns
    SUSPICIOUS_PATTERNS = [
        r'[<>"\']',  # HTML/XSS patterns
        r'(union|select|insert|delete|drop|create)',  # SQL injection patterns
        r'(script|javascript|vbscript)',  # Script injection
        r'(\.\.\/|\.\.\\)',  # Path traversal
    ]

    def __init__(self):
        self.suspicious_pattern_regex = re.compile(
            '|'.join(self.SUSPICIOUS_PATTERNS),
            re.IGNORECASE
        )

    def validate_jwt_token(self, token: str) -> tuple[bool, Optional[str]]:
        """
        Validate JWT token format and detect suspicious patterns.

        Args:
            token: JWT token to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not token:
            return False, "Empty token"

        # Check token length
        if len(token) > self.MAX_TOKEN_LENGTH:
            logger.warning(f"JWT token too long: {len(token)} characters")
            return False, "Token too long"

        # Check token format (basic JWT structure validation)
        if not self.JWT_TOKEN_PATTERN.match(token):
            logger.warning("Invalid JWT token format")
            return False, "Invalid token format"

        # Check for suspicious patterns
        if self.suspicious_pattern_regex.search(token):
            logger.warning("Suspicious patterns detected in JWT token")
            return False, "Invalid token content"

        return True, None

    def validate_request_data(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate request data for suspicious patterns.

        Args:
            data: Dictionary of request data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        for key, value in data.items():
            if isinstance(value, str):
                if self.suspicious_pattern_regex.search(value):
                    logger.warning(f"Suspicious pattern detected in field '{key}': {value[:100]}")
                    return False, f"Invalid content in field '{key}'"

        return True, None

    def log_security_event(self, request: HttpRequest, event_type: str, details: Dict[str, Any]) -> None:
        """
        Log security-related events for monitoring.

        Args:
            request: Django HTTP request
            event_type: Type of security event
            details: Additional event details
        """
        client_ip = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')

        security_event = {
            'timestamp': timezone.now().isoformat(),
            'event_type': event_type,
            'client_ip': client_ip,
            'user_agent': user_agent,
            'path': request.path,
            'method': request.method,
            **details
        }

        logger.warning(f"Security event: {event_type} - {security_event}")

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip

    def check_rate_limit_exceeded(self, request: HttpRequest, identifier: str, max_attempts: int = 10, window_seconds: int = 300) -> bool:
        """
        Check if rate limit has been exceeded for a specific identifier.

        Args:
            request: Django HTTP request
            identifier: Unique identifier (IP, user, etc.)
            max_attempts: Maximum attempts allowed
            window_seconds: Time window in seconds

        Returns:
            True if rate limit exceeded, False otherwise
        """
        cache_key = f"security_rate_limit:{identifier}"
        current_attempts = cache.get(cache_key, 0)

        if current_attempts >= max_attempts:
            self.log_security_event(request, 'rate_limit_exceeded', {
                'identifier': identifier,
                'attempts': current_attempts,
                'max_attempts': max_attempts
            })
            return True

        # Increment counter
        cache.set(cache_key, current_attempts + 1, window_seconds)
        return False


class SecurityHeaders:
    """Security headers management for responses."""

    @staticmethod
    def add_security_headers(response):
        """
        Add security headers to HTTP response.

        Args:
            response: Django HttpResponse object
        """
        # Prevent caching of authentication responses
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        # Content security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'

        return response


# Singleton instances
security_validator = SecurityValidator()