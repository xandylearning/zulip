"""
User Mapping Utility

Maps LMS users (students/mentors) to Zulip UserProfiles for notifications.
"""

import logging
from typing import Dict, Optional, Tuple
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings

from lms_integration.models import Students, Mentors

logger = logging.getLogger(__name__)
User = get_user_model()


class UserMapper:
    """
    Maps LMS users to Zulip UserProfiles for notifications.
    """
    
    CACHE_PREFIX = 'lms_user_mapping'
    CACHE_TIMEOUT = 3600  # 1 hour
    
    def __init__(self):
        self.cache_enabled = hasattr(settings, 'CACHES')
    
    def get_zulip_user_for_student(self, student_id: int) -> Optional[User]:
        """
        Get Zulip UserProfile for LMS student.
        
        Args:
            student_id: LMS student ID
            
        Returns:
            Zulip User instance or None if not found
        """
        cache_key = f"{self.CACHE_PREFIX}_student_{student_id}"
        
        # Try cache first
        if self.cache_enabled:
            cached_user = cache.get(cache_key)
            if cached_user:
                return cached_user
        
        try:
            # Get student from LMS
            student = Students.objects.using('lms_db').get(id=student_id)
            
            if not student.email:
                logger.warning(f"Student {student_id} has no email address")
                return None
            
            # Find Zulip user by email
            zulip_user = User.objects.filter(email=student.email).first()
            
            if zulip_user:
                # Cache the result
                if self.cache_enabled:
                    cache.set(cache_key, zulip_user, self.CACHE_TIMEOUT)
                logger.info(f"Mapped LMS student {student_id} to Zulip user {zulip_user.id}")
            else:
                logger.warning(f"No Zulip user found for student {student_id} (email: {student.email})")
            
            return zulip_user
            
        except Students.DoesNotExist:
            logger.warning(f"LMS student {student_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error mapping student {student_id} to Zulip user: {e}")
            return None
    
    def get_zulip_user_for_mentor(self, mentor_id: int) -> Optional[User]:
        """
        Get Zulip UserProfile for LMS mentor.
        
        Args:
            mentor_id: LMS mentor ID
            
        Returns:
            Zulip User instance or None if not found
        """
        cache_key = f"{self.CACHE_PREFIX}_mentor_{mentor_id}"
        
        # Try cache first
        if self.cache_enabled:
            cached_user = cache.get(cache_key)
            if cached_user:
                return cached_user
        
        try:
            # Get mentor from LMS
            mentor = Mentors.objects.using('lms_db').get(user_id=mentor_id)
            
            if not mentor.email:
                logger.warning(f"Mentor {mentor_id} has no email address")
                return None
            
            # Find Zulip user by email
            zulip_user = User.objects.filter(email=mentor.email).first()
            
            if zulip_user:
                # Cache the result
                if self.cache_enabled:
                    cache.set(cache_key, zulip_user, self.CACHE_TIMEOUT)
                logger.info(f"Mapped LMS mentor {mentor_id} to Zulip user {zulip_user.id}")
            else:
                logger.warning(f"No Zulip user found for mentor {mentor_id} (email: {mentor.email})")
            
            return zulip_user
            
        except Mentors.DoesNotExist:
            logger.warning(f"LMS mentor {mentor_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error mapping mentor {mentor_id} to Zulip user: {e}")
            return None
    
    def get_mentor_for_student(self, student_id: int) -> Optional[Tuple[int, str]]:
        """
        Get mentor information for a student.
        
        Args:
            student_id: LMS student ID
            
        Returns:
            Tuple of (mentor_id, mentor_username) or None if not found
        """
        cache_key = f"{self.CACHE_PREFIX}_student_mentor_{student_id}"
        
        # Try cache first
        if self.cache_enabled:
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        
        try:
            from lms_integration.models import Mentortostudent
            
            # Find mentor-student relationship
            mentor_student = Mentortostudent.objects.using('lms_db').filter(
                b_id=student_id  # b is the student in the relationship
            ).select_related('a').first()  # a is the mentor
            
            if mentor_student and mentor_student.a:
                mentor = mentor_student.a
                result = (mentor.user_id, mentor.username)
                
                # Cache the result
                if self.cache_enabled:
                    cache.set(cache_key, result, self.CACHE_TIMEOUT)
                
                return result
            else:
                logger.warning(f"No mentor found for student {student_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error finding mentor for student {student_id}: {e}")
            return None
    
    def get_notification_recipients(self, student_id: int) -> list:
        """
        Get list of Zulip users who should receive notifications for a student.
        
        Args:
            student_id: LMS student ID
            
        Returns:
            List of Zulip User instances
        """
        recipients = []
        
        # Get mentor for the student
        mentor_info = self.get_mentor_for_student(student_id)
        if mentor_info:
            mentor_id, mentor_username = mentor_info
            mentor_user = self.get_zulip_user_for_mentor(mentor_id)
            if mentor_user:
                recipients.append(mentor_user)
        
        # Could add additional recipients here (e.g., supervisors, admins)
        # based on configuration or student attributes
        
        return recipients
    
    def clear_cache(self, student_id: Optional[int] = None, mentor_id: Optional[int] = None):
        """
        Clear user mapping cache.
        
        Args:
            student_id: Clear cache for specific student (optional)
            mentor_id: Clear cache for specific mentor (optional)
        """
        if not self.cache_enabled:
            return
        
        if student_id:
            cache_key = f"{self.CACHE_PREFIX}_student_{student_id}"
            cache.delete(cache_key)
            cache_key = f"{self.CACHE_PREFIX}_student_mentor_{student_id}"
            cache.delete(cache_key)
            logger.info(f"Cleared cache for student {student_id}")
        
        if mentor_id:
            cache_key = f"{self.CACHE_PREFIX}_mentor_{mentor_id}"
            cache.delete(cache_key)
            logger.info(f"Cleared cache for mentor {mentor_id}")
        
        if not student_id and not mentor_id:
            # Clear all LMS user mapping cache
            # Note: This is a simple implementation - in production you might want
            # to use cache versioning or more sophisticated cache invalidation
            logger.info("Cleared all LMS user mapping cache")
    
    def get_mapping_stats(self) -> Dict[str, int]:
        """
        Get statistics about user mappings.
        
        Returns:
            Dictionary with mapping statistics
        """
        stats = {
            'total_students': 0,
            'total_mentors': 0,
            'mapped_students': 0,
            'mapped_mentors': 0,
        }
        
        try:
            # Count total students and mentors in LMS
            stats['total_students'] = Students.objects.using('lms_db').count()
            stats['total_mentors'] = Mentors.objects.using('lms_db').count()
            
            # Count mapped users (this is approximate - in production you might
            # want to track this more precisely)
            # For now, we'll just return the totals
            stats['mapped_students'] = 0  # Would need to implement proper counting
            stats['mapped_mentors'] = 0   # Would need to implement proper counting
            
        except Exception as e:
            logger.error(f"Error getting mapping stats: {e}")
        
        return stats
