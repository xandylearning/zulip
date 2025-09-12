"""
Django management command to list available event listeners
"""

from django.core.management.base import BaseCommand
from zerver.event_listeners.models import EventListener, ListenerStats
from zerver.event_listeners.registry import event_listener_registry


class Command(BaseCommand):
    """
    List available event listeners
    """
    
    help = 'List available event listeners'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--show-stats',
            action='store_true',
            help='Show listener statistics'
        )
        parser.add_argument(
            '--show-config',
            action='store_true',
            help='Show listener configurations'
        )
        parser.add_argument(
            '--format',
            choices=['table', 'json'],
            default='table',
            help='Output format'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        
        show_stats = options['show_stats']
        show_config = options['show_config']
        output_format = options['format']
        
        if output_format == 'json':
            self.output_json(show_stats, show_config)
        else:
            self.output_table(show_stats, show_config)
    
    def output_table(self, show_stats, show_config):
        """Output in table format"""
        
        # Registered listeners (from registry)
        self.stdout.write("\nRegistered Event Listener Classes:")
        self.stdout.write("=" * 60)
        
        registered_listeners = event_listener_registry.list_listeners()
        if registered_listeners:
            for name in registered_listeners:
                handler_class = event_listener_registry.get_handler_class(name)
                supported_events = getattr(handler_class, 'supported_events', [])
                description = getattr(handler_class, 'description', 'No description')
                
                self.stdout.write(f"Name: {name}")
                self.stdout.write(f"  Class: {handler_class.__name__}")
                self.stdout.write(f"  Description: {description}")
                self.stdout.write(f"  Supported Events: {', '.join(supported_events)}")
                self.stdout.write("")
        else:
            self.stdout.write("No registered listeners found")
        
        # Active listeners (from database)
        self.stdout.write("\nActive Event Listeners:")
        self.stdout.write("=" * 60)
        
        active_listeners = EventListener.objects.all().order_by('name')
        if active_listeners:
            for listener in active_listeners:
                status = "ENABLED" if listener.enabled else "DISABLED"
                self.stdout.write(f"Name: {listener.name} [{status}]")
                self.stdout.write(f"  Description: {listener.description or 'No description'}")
                self.stdout.write(f"  Event Types: {', '.join(listener.event_types)}")
                self.stdout.write(f"  Handler: {listener.handler_module}.{listener.handler_class}")
                
                if listener.realm:
                    self.stdout.write(f"  Realm: {listener.realm.string_id}")
                
                if show_config and listener.handler_config:
                    self.stdout.write(f"  Config: {listener.handler_config}")
                
                if show_stats:
                    try:
                        stats = listener.listenerstats
                        success_rate = 0
                        if stats.total_events_processed > 0:
                            success_rate = (stats.successful_events / stats.total_events_processed) * 100
                        
                        self.stdout.write(f"  Stats:")
                        self.stdout.write(f"    Total Events: {stats.total_events_processed}")
                        self.stdout.write(f"    Success Rate: {success_rate:.1f}%")
                        self.stdout.write(f"    Avg Processing Time: {stats.average_processing_time_ms:.1f}ms")
                        if stats.last_event_processed_at:
                            self.stdout.write(f"    Last Event: {stats.last_event_processed_at}")
                        if stats.last_error:
                            self.stdout.write(f"    Last Error: {stats.last_error[:100]}...")
                    except ListenerStats.DoesNotExist:
                        self.stdout.write(f"  Stats: No statistics available")
                
                self.stdout.write("")
        else:
            self.stdout.write("No active listeners found")
    
    def output_json(self, show_stats, show_config):
        """Output in JSON format"""
        import json
        
        result = {
            'registered_listeners': [],
            'active_listeners': []
        }
        
        # Registered listeners
        for name in event_listener_registry.list_listeners():
            handler_class = event_listener_registry.get_handler_class(name)
            result['registered_listeners'].append({
                'name': name,
                'class': handler_class.__name__,
                'module': handler_class.__module__,
                'description': getattr(handler_class, 'description', ''),
                'supported_events': getattr(handler_class, 'supported_events', [])
            })
        
        # Active listeners
        for listener in EventListener.objects.all():
            listener_data = {
                'id': listener.id,
                'name': listener.name,
                'description': listener.description,
                'enabled': listener.enabled,
                'event_types': listener.event_types,
                'handler_module': listener.handler_module,
                'handler_class': listener.handler_class,
                'realm_id': listener.realm_id,
                'created_at': listener.created_at.isoformat(),
                'updated_at': listener.updated_at.isoformat()
            }
            
            if show_config:
                listener_data['handler_config'] = listener.handler_config
                listener_data['user_filter'] = listener.user_filter
            
            if show_stats:
                try:
                    stats = listener.listenerstats
                    listener_data['stats'] = {
                        'total_events_processed': stats.total_events_processed,
                        'successful_events': stats.successful_events,
                        'failed_events': stats.failed_events,
                        'average_processing_time_ms': stats.average_processing_time_ms,
                        'last_event_processed_at': stats.last_event_processed_at.isoformat() if stats.last_event_processed_at else None,
                        'is_running': stats.is_running,
                        'last_error': stats.last_error,
                        'last_error_at': stats.last_error_at.isoformat() if stats.last_error_at else None
                    }
                except ListenerStats.DoesNotExist:
                    listener_data['stats'] = None
            
            result['active_listeners'].append(listener_data)
        
        self.stdout.write(json.dumps(result, indent=2, default=str))