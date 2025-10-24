"""
LMS Activity Event Listeners

Event listeners for processing LMS activity events and sending notifications.
"""

import logging
from typing import List
from django.conf import settings
from django.db import transaction

from zerver.event_listeners.base import BaseEventHandler
from zerver.actions.message_send import internal_send_private_message
from zerver.models import UserProfile

from lms_integration.models import LMSActivityEvent, LMSEventLog
from lms_integration.lib.message_formatter import MessageFormatter
from lms_integration.lib.user_mapping import UserMapper

logger = logging.getLogger(__name__)


class LMSActivityEventHandler(BaseEventHandler):
    """
    Event handler for LMS activity events.
    Processes events and sends notifications to mentors.
    """
    
    def __init__(self):
        self.message_formatter = MessageFormatter()
        self.user_mapper = UserMapper()
        self.notifications_enabled = getattr(settings, 'LMS_NOTIFY_MENTORS_ENABLED', True)
    
    def handle_event(self, event_data: dict) -> None:
        """
        Handle LMS activity event.
        
        Args:
            event_data: Event data dictionary
        """
        try:
            event_id = event_data.get('event_id')
            if not event_id:
                logger.error("Event data missing event_id")
                return
            
            # Get the event from database
            try:
                event = LMSActivityEvent.objects.get(event_id=event_id)
            except LMSActivityEvent.DoesNotExist:
                logger.error(f"LMS activity event {event_id} not found")
                return
            
            # Process the event
            self._process_event(event)
            
        except Exception as e:
            logger.error(f"Error handling LMS activity event: {e}")
    
    def _process_event(self, event: LMSActivityEvent) -> None:
        """
        Process a single LMS activity event.
        
        Args:
            event: LMSActivityEvent instance
        """
        try:
            # Create event log entry
            event_log = LMSEventLog.objects.create(event=event)
            
            # Send notification if enabled
            if self.notifications_enabled:
                self._send_notification(event, event_log)
            else:
                logger.info(f"Notifications disabled, skipping notification for event {event.event_id}")
            
            # Mark as processed for AI
            event.processed_for_ai = True
            event.save(update_fields=['processed_for_ai'])
            
            logger.info(f"Successfully processed LMS activity event {event.event_id}")
            
        except Exception as e:
            logger.error(f"Error processing event {event.event_id}: {e}")
            # Update event log with error
            try:
                event_log = LMSEventLog.objects.get(event=event)
                event_log.error_message = str(e)
                event_log.save(update_fields=['error_message'])
            except LMSEventLog.DoesNotExist:
                # Create error log entry
                LMSEventLog.objects.create(
                    event=event,
                    error_message=str(e)
                )
    
    def _send_notification(self, event: LMSActivityEvent, event_log: LMSEventLog) -> None:
        """
        Send notification to mentor(s) for the event.
        
        Args:
            event: LMSActivityEvent instance
            event_log: LMSEventLog instance
        """
        try:
            # Get notification recipients
            recipients = self._get_notification_recipients(event)
            
            if not recipients:
                logger.warning(f"No recipients found for event {event.event_id}")
                event_log.error_message = "No notification recipients found"
                event_log.save(update_fields=['error_message'])
                return
            
            # Format notification message
            message = self.message_formatter.format_notification_message(event)
            
            # Send notification to each recipient
            for recipient in recipients:
                try:
                    # Send private message
                    message_id = internal_send_private_message(
                        sender=recipient,  # Use recipient as sender for system messages
                        recipient=recipient,
                        content=message,
                        realm=recipient.realm
                    )
                    
                    # Update event log
                    event_log.notification_sent = True
                    event_log.notification_message_id = message_id
                    event_log.save(update_fields=['notification_sent', 'notification_message_id'])
                    
                    logger.info(f"Sent notification to {recipient.email} for event {event.event_id}")
                    
                except Exception as e:
                    logger.error(f"Error sending notification to {recipient.email}: {e}")
                    event_log.error_message = f"Failed to send notification: {e}"
                    event_log.save(update_fields=['error_message'])
            
        except Exception as e:
            logger.error(f"Error sending notification for event {event.event_id}: {e}")
            event_log.error_message = f"Notification error: {e}"
            event_log.save(update_fields=['error_message'])
    
    def _get_notification_recipients(self, event: LMSActivityEvent) -> List[UserProfile]:
        """
        Get list of users who should receive notifications for this event.
        
        Args:
            event: LMSActivityEvent instance
            
        Returns:
            List of UserProfile instances
        """
        recipients = []
        
        try:
            # Get mentor for the student
            if event.mentor_id:
                mentor_user = self.user_mapper.get_zulip_user_for_mentor(event.mentor_id)
                if mentor_user:
                    recipients.append(mentor_user)
                else:
                    logger.warning(f"No Zulip user found for mentor {event.mentor_id}")
            
            # If no mentor found, try to find mentor by student ID
            if not recipients and event.student_id:
                mentor_recipients = self.user_mapper.get_notification_recipients(event.student_id)
                recipients.extend(mentor_recipients)
            
            # If still no recipients, log warning
            if not recipients:
                logger.warning(f"No notification recipients found for event {event.event_id}")
            
        except Exception as e:
            logger.error(f"Error getting notification recipients for event {event.event_id}: {e}")
        
        return recipients
    
    def process_pending_events(self) -> int:
        """
        Process all pending LMS activity events.
        
        Returns:
            Number of events processed
        """
        processed_count = 0
        
        try:
            # Get all unprocessed events
            pending_events = LMSActivityEvent.objects.filter(processed_for_ai=False)
            
            logger.info(f"Processing {pending_events.count()} pending LMS activity events")
            
            for event in pending_events:
                try:
                    self._process_event(event)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing event {event.event_id}: {e}")
            
            logger.info(f"Processed {processed_count} LMS activity events")
            
        except Exception as e:
            logger.error(f"Error processing pending events: {e}")
        
        return processed_count
    
    def get_event_stats(self) -> dict:
        """
        Get statistics about LMS activity events.
        
        Returns:
            Dictionary with event statistics
        """
        stats = {
            'total_events': 0,
            'processed_events': 0,
            'pending_events': 0,
            'events_with_notifications': 0,
            'events_with_errors': 0,
        }
        
        try:
            stats['total_events'] = LMSActivityEvent.objects.count()
            stats['processed_events'] = LMSActivityEvent.objects.filter(processed_for_ai=True).count()
            stats['pending_events'] = LMSActivityEvent.objects.filter(processed_for_ai=False).count()
            
            # Count events with successful notifications
            stats['events_with_notifications'] = LMSEventLog.objects.filter(
                notification_sent=True
            ).count()
            
            # Count events with errors
            stats['events_with_errors'] = LMSEventLog.objects.exclude(
                error_message__isnull=True
            ).exclude(error_message='').count()
            
        except Exception as e:
            logger.error(f"Error getting event stats: {e}")
        
        return stats
