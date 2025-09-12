"""
Models for the Event Listeners Django app
"""

from django.db import models
from zerver.models import UserProfile, Realm
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json


class EventListener(models.Model):
    """Model to store event listener configurations"""
    
    name = models.CharField(max_length=100, unique=True, help_text="Unique name for the event listener")
    description = models.TextField(blank=True, help_text="Description of what this listener does")
    
    # Event configuration
    event_types = models.JSONField(default=list, help_text="List of event types to listen for")
    enabled = models.BooleanField(default=True, help_text="Whether this listener is active")
    
    # Handler configuration
    handler_module = models.CharField(max_length=200, help_text="Python module path for the handler")
    handler_class = models.CharField(max_length=100, help_text="Handler class name")
    handler_config = models.JSONField(default=dict, help_text="Configuration for the handler")
    
    # Filtering
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE, null=True, blank=True, 
                             help_text="Restrict to specific realm (null for all realms)")
    user_filter = models.JSONField(default=dict, blank=True, 
                                  help_text="User filtering criteria")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Event Listener"
        verbose_name_plural = "Event Listeners"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_handler_class(self):
        """Dynamically import and return the handler class"""
        module_path, class_name = self.handler_module, self.handler_class
        
        try:
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Cannot import handler {module_path}.{class_name}: {e}")
    
    def is_active(self):
        """Check if listener is active and properly configured"""
        return (
            self.enabled and 
            self.handler_module and 
            self.handler_class and 
            self.event_types
        )


class EventLog(models.Model):
    """Model to log processed events for debugging and monitoring"""
    
    listener = models.ForeignKey(EventListener, on_delete=models.CASCADE)
    
    # Event information
    event_type = models.CharField(max_length=50)
    event_id = models.BigIntegerField()
    event_data = models.JSONField(help_text="Event payload")
    
    # Processing information
    processed_at = models.DateTimeField(auto_now_add=True)
    processing_time_ms = models.IntegerField(help_text="Processing time in milliseconds")
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    # Context
    user_id = models.IntegerField(null=True, blank=True)
    realm_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Event Log"
        verbose_name_plural = "Event Logs"
        ordering = ['-processed_at']
        indexes = [
            models.Index(fields=['listener', 'event_type']),
            models.Index(fields=['processed_at']),
            models.Index(fields=['success']),
        ]
    
    def __str__(self):
        return f"{self.listener.name} - {self.event_type} ({self.processed_at})"


class ListenerStats(models.Model):
    """Model to store listener statistics"""
    
    listener = models.OneToOneField(EventListener, on_delete=models.CASCADE, primary_key=True)
    
    # Counters
    total_events_processed = models.BigIntegerField(default=0)
    successful_events = models.BigIntegerField(default=0)
    failed_events = models.BigIntegerField(default=0)
    
    # Timing
    average_processing_time_ms = models.FloatField(default=0.0)
    last_event_processed_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_running = models.BooleanField(default=False)
    last_error = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Listener Statistics"
        verbose_name_plural = "Listener Statistics"
    
    def __str__(self):
        return f"Stats for {self.listener.name}"
    
    def update_stats(self, processing_time_ms: int, success: bool = True, error: str = None):
        """Update statistics after processing an event"""
        from django.utils import timezone
        
        self.total_events_processed += 1
        if success:
            self.successful_events += 1
        else:
            self.failed_events += 1
            if error:
                self.last_error = error
                self.last_error_at = timezone.now()
        
        # Update average processing time
        if self.total_events_processed == 1:
            self.average_processing_time_ms = processing_time_ms
        else:
            # Running average
            self.average_processing_time_ms = (
                (self.average_processing_time_ms * (self.total_events_processed - 1) + processing_time_ms) / 
                self.total_events_processed
            )
        
        self.last_event_processed_at = timezone.now()
        self.save()


class ListenerConfig(models.Model):
    """Model for storing listener-specific configuration"""
    
    listener = models.ForeignKey(EventListener, on_delete=models.CASCADE, related_name='configs')
    key = models.CharField(max_length=100)
    value = models.JSONField()
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['listener', 'key']
        verbose_name = "Listener Configuration"
        verbose_name_plural = "Listener Configurations"
    
    def __str__(self):
        return f"{self.listener.name}.{self.key}"