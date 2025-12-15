"""
TestPress JWT Token Validator

This module handles validation of JWT tokens by calling the TestPress API
to verify the token and retrieve user information.
"""

import logging
import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TestPressJWTValidator:
    """Validates JWT tokens against TestPress API and caches results."""

    def __init__(self):
        self.api_base_url = getattr(settings, 'TESTPRESS_API_BASE_URL', 'https://learn.xandylearning.com/api/v2.5/')
        self.user_info_endpoint = 'me'
        self.cache_timeout = getattr(settings, 'TESTPRESS_TOKEN_CACHE_SECONDS', 300)  # 5 minutes
        self.request_timeout = getattr(settings, 'TESTPRESS_REQUEST_TIMEOUT', 10)  # 10 seconds

    def _get_cache_key(self, token: str) -> str:
        """Generate cache key for JWT token."""
        # Use first 16 chars of token for cache key to avoid storing full token
        token_prefix = token[:16] if len(token) > 16 else token
        return f"testpress_jwt_validation:{token_prefix}"

    def _make_api_request(self, token: str) -> Optional[Dict[str, Any]]:
        """Make API request to TestPress /me endpoint."""
        try:
            url = f"{self.api_base_url.rstrip('/')}/{self.user_info_endpoint}"
            headers = {
                'Authorization': f'JWT {token}',
                'Content-Type': 'application/json',
            }

            logger.info("Making TestPress API request to validate JWT token")
            response = requests.get(
                url,
                headers=headers,
                timeout=self.request_timeout
            )

            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"TestPress JWT validation successful for user: {user_data.get('email', 'unknown')}")
                return user_data
            elif response.status_code == 401:
                logger.warning("TestPress JWT validation failed: Invalid or expired token")
                return None
            else:
                logger.error(f"TestPress API returned unexpected status code: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.error("TestPress API request timed out")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("TestPress API connection error")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"TestPress API request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during TestPress API validation: {str(e)}")
            return None

    def validate_token(self, token: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token against TestPress API.

        Args:
            token: JWT token to validate
            use_cache: Whether to use cached validation results

        Returns:
            Dict containing user data if valid, None if invalid
        """
        if not token:
            logger.warning("Empty JWT token provided for validation")
            return None

        cache_key = self._get_cache_key(token)

        # Check cache first if enabled
        if use_cache:
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                if cached_result == 'INVALID':
                    logger.debug("Found cached invalid token result")
                    return None
                logger.debug("Found cached valid token result")
                return cached_result

        # Make API request to validate token
        user_data = self._make_api_request(token)

        # Cache the result
        if use_cache:
            if user_data is None:
                # Cache invalid tokens for shorter time to allow for quick retry
                cache.set(cache_key, 'INVALID', timeout=60)
            else:
                cache.set(cache_key, user_data, timeout=self.cache_timeout)

        return user_data

    def clear_token_cache(self, token: str) -> None:
        """Clear cached validation result for a specific token."""
        cache_key = self._get_cache_key(token)
        cache.delete(cache_key)
        logger.debug(f"Cleared cache for token: {cache_key}")


# Singleton instance for use across the application
testpress_jwt_validator = TestPressJWTValidator()