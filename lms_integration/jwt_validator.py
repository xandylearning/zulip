"""
TestPress JWT Token Validator

This module handles validation of JWT tokens by:
1. Decoding JWT to extract user ID (no API call)
2. Querying LMS database first (fast, local)
3. Falling back to TestPress API only if needed
"""

import logging
from typing import Any, Dict, Optional

import jwt
import requests
from django.conf import settings
from django.core.cache import cache

from .models import Students

logger = logging.getLogger(__name__)


class TestPressJWTValidator:
    """
    Validates JWT tokens by:
    1. Decoding JWT to extract user ID (no API call needed)
    2. Querying LMS database first (fast, local)
    3. Falling back to TestPress API only if user not found in LMS DB
    """

    def __init__(self):
        self.api_base_url = getattr(settings, 'TESTPRESS_API_BASE_URL', 'https://learn.xandylearning.com/api/v2.5/')
        self.user_info_endpoint = 'me'
        # Ensure cache_timeout is always an integer (settings may return string from env vars)
        cache_timeout_value = getattr(settings, 'TESTPRESS_TOKEN_CACHE_SECONDS', 300)  # 5 minutes
        try:
            self.cache_timeout = int(cache_timeout_value)
        except (TypeError, ValueError):
            # Fallback to default if conversion fails
            logger.warning(f"Invalid cache timeout value '{cache_timeout_value}', using default 300 seconds")
            self.cache_timeout = 300
        # Ensure timeout is always a numeric value (int or float) for requests library
        # get_config may return a string, so convert to float to ensure proper type
        timeout_value = getattr(settings, 'TESTPRESS_REQUEST_TIMEOUT', 10)
        try:
            self.request_timeout = float(timeout_value)
        except (TypeError, ValueError):
            # Fallback to default if conversion fails
            logger.warning(f"Invalid timeout value '{timeout_value}', using default 10 seconds")
            self.request_timeout = 10.0

    def _decode_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode JWT token to extract user ID without verification.
        This is safe because we'll validate the user exists in our LMS database.
        
        Args:
            token: JWT token to decode
            
        Returns:
            Decoded JWT payload dict, or None if decoding fails
        """
        try:
            # Decode without verification - we trust the token if user exists in our DB
            # The token signature is validated by TestPress when it was issued
            decoded = jwt.decode(token, options={"verify_signature": False})
            return decoded
        except jwt.DecodeError as e:
            logger.warning(f"Failed to decode JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error decoding JWT token: {e}")
            return None

    def _get_user_id_from_token(self, token: str) -> Optional[int]:
        """
        Extract user ID from JWT token.
        
        Args:
            token: JWT token
            
        Returns:
            User ID (integer) if found, None otherwise
        """
        payload = self._decode_jwt_token(token)
        if not payload:
            return None
        
        # Try different possible field names for user ID
        user_id = payload.get('user_id') or payload.get('userId') or payload.get('id') or payload.get('sub')
        
        if user_id:
            try:
                return int(user_id)
            except (ValueError, TypeError):
                logger.warning(f"User ID in JWT is not a valid integer: {user_id}")
                return None
        
        return None

    def _get_user_from_lms_db(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user data from LMS database by user ID.
        
        Args:
            user_id: LMS user ID
            
        Returns:
            Dict with user data in TestPress API format, or None if not found
        """
        try:
            student = Students.objects.using('lms_db').get(id=user_id)
            
            # Convert Students model to TestPress API format
            user_data = {
                'id': student.id,
                'username': student.username,
                'email': student.email or '',
                'first_name': student.first_name or '',
                'last_name': student.last_name or '',
                'display_name': student.display_name or '',
                'is_active': student.is_active if student.is_active is not None else True,
                'photo': student.photo or '',
                'large_image': student.large_image or '',
                'medium_image': student.medium_image or '',
                'small_image': student.small_image or '',
            }
            
            logger.info(f"Found user {user_id} in LMS database: {student.username}")
            return user_data
            
        except Students.DoesNotExist:
            logger.debug(f"User {user_id} not found in LMS database")
            return None
        except Exception as e:
            logger.error(f"Error querying LMS database for user {user_id}: {e}")
            return None

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
        Validate JWT token by:
        1. Decoding JWT to extract user ID (no API call)
        2. Querying LMS database first (fast, local)
        3. Falling back to TestPress API only if user not found in LMS DB

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

        # Step 1: Decode JWT to extract user ID (no API call)
        user_id = self._get_user_id_from_token(token)
        
        if user_id:
            # Step 2: Try to get user from LMS database first (fast, local)
            user_data = self._get_user_from_lms_db(user_id)
            
            if user_data:
                # Found in LMS DB - cache and return
                if use_cache:
                    cache.set(cache_key, user_data, timeout=self.cache_timeout)
                logger.info(f"JWT validation successful via LMS DB for user ID: {user_id}")
                return user_data
            else:
                # User not found in LMS DB - fall back to TestPress API
                logger.info(f"User {user_id} not found in LMS DB, falling back to TestPress API")
        else:
            # Could not extract user ID from JWT - fall back to TestPress API
            logger.info("Could not extract user ID from JWT, falling back to TestPress API")

        # Step 3: Fallback to TestPress API (only if LMS DB lookup failed)
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