"""
Event processing engine
Handles the core logic of processing events with registered listeners
"""

import logging
import time
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.db import transaction
from .models import EventListener, EventLog, ListenerStats
from .registry import event_listener_registry
from .base import BaseEventHandler

logger = logging.getLogger(__name__)


class EventProcessor:
    """
    Main event processor that coordinates event handling
    """
    
    def __init__(self):
        self.active_handlers: Dict[str, BaseEventHandler] = {}
        self.stats = {
            'total_events': 0,
            'successful_events': 0,
            'failed_events': 0,
            'start_time': timezone.now(),
        }
    
    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single event with all applicable listeners
        
        Args:
            event: The event dictionary
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        event_type = event.get('type', 'unknown')
        event_id = event.get('id', 0)
        
        self.stats['total_events'] += 1
        
        results = {
            'event_type': event_type,
            'event_id': event_id,
            'processed_listeners': [],
            'failed_listeners': [],
            'processing_time_ms': 0,
            'success': False
        }
        
        logger.debug(f"Processing event {event_type}:{event_id}")
        
        try:
            # Get active listeners for this event type
            active_listeners = self.get_active_listeners_for_event(event)
            
            if not active_listeners:
                logger.debug(f"No active listeners for event type: {event_type}")
                results['success'] = True  # No error if no listeners
                return results
            
            # Process with each listener
            for listener_config in active_listeners:
                listener_result = self.process_with_listener(event, listener_config)
                
                if listener_result['success']:
                    results['processed_listeners'].append(listener_result)
                else:
                    results['failed_listeners'].append(listener_result)
            
            # Overall success if at least one listener succeeded
            results['success'] = len(results['processed_listeners']) > 0
            
            if results['success']:
                self.stats['successful_events'] += 1
            else:
                self.stats['failed_events'] += 1
                
        except Exception as e:
            logger.error(f"Unexpected error processing event {event_type}:{event_id}: {e}")
            results['error'] = str(e)
            self.stats['failed_events'] += 1
        
        finally:
            results['processing_time_ms'] = int((time.time() - start_time) * 1000)
        
        return results
    
    def process_with_listener(self, event: Dict[str, Any], listener_config: EventListener) -> Dict[str, Any]:
        """
        Process event with a specific listener
        
        Args:
            event: The event dictionary
            listener_config: EventListener model instance
            
        Returns:
            Dictionary with processing result
        """
        start_time = time.time()
        
        result = {
            'listener_name': listener_config.name,
            'listener_id': listener_config.id,
            'success': False,
            'error': None,
            'processing_time_ms': 0
        }
        
        try:
            # Get or create handler instance
            handler = self.get_handler_instance(listener_config)
            if not handler:
                result['error'] = f"Failed to create handler instance"
                return result
            
            # Check if handler can process this event
            if not handler.can_handle_event(event):
                result['success'] = True  # Skip but don't count as error
                result['error'] = "Event type not supported by handler"
                return result
            
            # Pre-processing
            if not handler.pre_process(event):
                result['success'] = True  # Skip but don't count as error
                result['error'] = "Pre-processing filter excluded event"
                return result
            
            # Main processing
            success = handler.handle_event(event)
            result['success'] = success
            
            # Post-processing
            handler.post_process(event, success)
            
            if not success:
                result['error'] = "Handler returned False"
        
        except Exception as e:
            logger.error(f"Error in listener {listener_config.name}: {e}")
            result['error'] = str(e)
        
        finally:
            processing_time_ms = int((time.time() - start_time) * 1000)
            result['processing_time_ms'] = processing_time_ms
            
            # Update statistics
            self.update_listener_stats(listener_config, processing_time_ms, result['success'], result.get('error'))
            
            # Log event if enabled
            if getattr(listener_config, 'log_events', False):
                self.log_event(listener_config, event, result)
        
        return result
    
    def get_active_listeners_for_event(self, event: Dict[str, Any]) -> List[EventListener]:
        """
        Get all active listeners that can handle this event
        
        Args:
            event: The event dictionary
            
        Returns:
            List of EventListener instances
        """
        event_type = event.get('type')
        
        # Query active listeners that support this event type
        listeners = EventListener.objects.filter(
            enabled=True,
            event_types__contains=[event_type]
        ).select_related('realm')
        
        # Additional filtering based on event context
        filtered_listeners = []
        for listener in listeners:
            if self.listener_matches_event(listener, event):
                filtered_listeners.append(listener)
        
        return filtered_listeners
    
    def listener_matches_event(self, listener: EventListener, event: Dict[str, Any]) -> bool:
        """
        Check if a listener's filters match the event
        
        Args:
            listener: EventListener instance
            event: Event dictionary
            
        Returns:
            True if listener should process this event
        """
        # Realm filtering
        if listener.realm_id:
            event_realm_id = self.extract_realm_id(event)
            if event_realm_id and event_realm_id != listener.realm_id:
                return False
        
        # User filtering
        if listener.user_filter:
            user_id = self.extract_user_id(event)
            if user_id and not self.user_matches_filter(user_id, listener.user_filter):
                return False
        
        return True
    
    def extract_realm_id(self, event: Dict[str, Any]) -> Optional[int]:
        """Extract realm ID from event"""
        # This would need to be implemented based on event structure
        # For now, return None (no realm filtering)
        return None
    
    def extract_user_id(self, event: Dict[str, Any]) -> Optional[int]:
        """Extract user ID from event"""
        if event.get('type') == 'message':
            return event.get('message', {}).get('sender_id')
        elif event.get('type') in ['presence', 'user_status']:
            return event.get('user_id')
        elif event.get('type') == 'typing':
            return event.get('sender', {}).get('user_id')
        return None
    
    def user_matches_filter(self, user_id: int, user_filter: Dict[str, Any]) -> bool:
        """Check if user matches filter criteria"""
        # Implement user filtering logic based on your requirements
        # For example: role-based filtering, specific user IDs, etc.
        
        if 'user_ids' in user_filter:
            return user_id in user_filter['user_ids']
        
        if 'exclude_user_ids' in user_filter:
            return user_id not in user_filter['exclude_user_ids']
        
        # Add more filtering logic as needed
        return True
    
    def get_handler_instance(self, listener_config: EventListener) -> Optional[BaseEventHandler]:
        """
        Get or create handler instance for a listener
        
        Args:
            listener_config: EventListener model instance
            
        Returns:
            Handler instance or None if failed
        """
        cache_key = f"{listener_config.id}_{listener_config.updated_at.timestamp()}"
        
        if cache_key in self.active_handlers:
            return self.active_handlers[cache_key]
        
        try:
            handler_class = listener_config.get_handler_class()
            handler_instance = handler_class(listener_config.handler_config)
            
            self.active_handlers[cache_key] = handler_instance
            return handler_instance
            
        except Exception as e:
            logger.error(f"Failed to create handler for listener {listener_config.name}: {e}")
            return None
    
    def update_listener_stats(self, listener_config: EventListener, processing_time_ms: int, 
                             success: bool, error: Optional[str] = None) -> None:
        """Update statistics for a listener"""
        try:
            stats, created = ListenerStats.objects.get_or_create(
                listener=listener_config,
                defaults={'is_running': True}
            )
            stats.update_stats(processing_time_ms, success, error)
        except Exception as e:
            logger.error(f"Failed to update stats for listener {listener_config.name}: {e}")
    
    def log_event(self, listener_config: EventListener, event: Dict[str, Any], 
                  result: Dict[str, Any]) -> None:
        """Log event processing for debugging"""
        try:
            EventLog.objects.create(
                listener=listener_config,
                event_type=event.get('type', 'unknown'),
                event_id=event.get('id', 0),
                event_data=event,
                processing_time_ms=result['processing_time_ms'],
                success=result['success'],
                error_message=result.get('error', ''),
                user_id=self.extract_user_id(event),
                realm_id=self.extract_realm_id(event)
            )
        except Exception as e:
            logger.error(f"Failed to log event for listener {listener_config.name}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        uptime = timezone.now() - self.stats['start_time']
        
        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'active_handlers': len(self.active_handlers),
            'registered_listeners': len(event_listener_registry.listeners)
        }
    
    def cleanup(self) -> None:
        """Cleanup resources"""
        self.active_handlers.clear()


# Global processor instance
event_processor = EventProcessor()