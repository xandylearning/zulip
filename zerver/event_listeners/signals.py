"""
Django signals for event listener integration
"""

import logging
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from .models import EventListener, ListenerStats
from .processor import event_processor

logger = logging.getLogger(__name__)


@receiver(post_save, sender=EventListener)
def on_listener_saved(sender, instance, created, **kwargs):
    """Handle EventListener save"""
    if created:
        logger.info(f"New event listener created: {instance.name}")
        
        # Initialize stats
        ListenerStats.objects.get_or_create(listener=instance)
    else:
        logger.info(f"Event listener updated: {instance.name}")
        
        # Clear cached handler instances when config changes
        event_processor.active_handlers.clear()


@receiver(post_delete, sender=EventListener)
def on_listener_deleted(sender, instance, **kwargs):
    """Handle EventListener deletion"""
    logger.info(f"Event listener deleted: {instance.name}")
    
    # Clear cached handler instances
    event_processor.active_handlers.clear()


# You can add more signals here for other models or custom events