"""
Django management command to run the event listener daemon
"""

import logging
import time
from typing import Any
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import zulip

from zerver.event_listeners.processor import event_processor
from zerver.event_listeners.models import EventListener, ListenerStats
from zerver.event_listeners.registry import event_listener_registry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to run the event listener daemon
    """
    
    help = 'Run the Event Listener daemon'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--config-file',
            type=str,
            default='~/.zuliprc',
            help='Path to Zulip configuration file'
        )
        parser.add_argument(
            '--listeners',
            nargs='+',
            help='Specific listeners to run (default: all active)'
        )
        parser.add_argument(
            '--event-types',
            nargs='+',
            help='Specific event types to listen for'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually processing events'
        )
        parser.add_argument(
            '--stats-interval',
            type=int,
            default=300,
            help='Interval in seconds to print statistics (0 to disable)'
        )
        parser.add_argument(
            '--demo-mode',
            action='store_true',
            help='Run in demo mode without Zulip client (for testing)'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        
        # Check if event listeners are enabled
        if not getattr(settings, 'EVENT_LISTENERS_ENABLED', False):
            raise CommandError(
                "Event listeners are not enabled. Set EVENT_LISTENERS_ENABLED = True in settings."
            )
        
        self.stdout.write("Starting Event Listener Daemon...")
        
        # Initialize
        self.config_file = options['config_file']
        self.specific_listeners = options.get('listeners')
        self.event_types = options.get('event_types')
        self.dry_run = options['dry_run']
        self.stats_interval = options['stats_interval']
        self.demo_mode = options['demo_mode']
        
        # In demo mode, show registered listeners
        if self.demo_mode:
            self.show_registered_listeners()
            if not self.dry_run:
                self.run_demo_mode()
            return
        
        # Validate configuration
        self.validate_setup()
        
        if self.dry_run:
            self.stdout.write("DRY RUN MODE - No events will be processed")
            self.show_configuration()
            return
        
        # Start the daemon
        self.run_daemon()
    
    def validate_setup(self):
        """Validate the setup before starting"""
        
        # Skip Zulip client validation in demo mode
        if self.demo_mode:
            self.stdout.write("Running in demo mode - skipping Zulip client validation")
        else:
            # Check Zulip client configuration
            try:
                client = zulip.Client(config_file=self.config_file)
                result = client.get_profile()
                if result['result'] != 'success':
                    raise CommandError(f"Zulip client connection failed: {result}")
                
                self.stdout.write(f"Connected to Zulip as: {result['full_name']} ({result['email']})")
                
            except Exception as e:
                raise CommandError(f"Failed to initialize Zulip client: {e}")
        
        # Check for registered listeners
        registered_listeners = event_listener_registry.list_listeners()
        if not registered_listeners:
            self.stdout.write("Warning: No event listeners registered")
            return
        
        self.stdout.write(f"Found {len(registered_listeners)} registered listeners")
        
        # Validate specific listeners if provided
        if self.specific_listeners:
            for name in self.specific_listeners:
                if name not in registered_listeners:
                    raise CommandError(f"Listener '{name}' not found. Available: {registered_listeners}")
    
    def get_active_listeners(self):
        """Get list of active listeners"""
        queryset = EventListener.objects.filter(enabled=True)
        
        if self.specific_listeners:
            queryset = queryset.filter(name__in=self.specific_listeners)
        
        return list(queryset)
    
    def show_configuration(self):
        """Show current configuration"""
        self.stdout.write("\nConfiguration:")
        self.stdout.write(f"  Config file: {self.config_file}")
        self.stdout.write(f"  Event types: {self.event_types or 'all'}")
        self.stdout.write(f"  Specific listeners: {self.specific_listeners or 'all active'}")
        
        active_listeners = self.get_active_listeners()
        self.stdout.write(f"\nActive listeners ({len(active_listeners)}):")
        for listener in active_listeners:
            self.stdout.write(f"  - {listener.name}: {listener.event_types}")
    
    def run_daemon(self):
        """Run the event listener daemon"""
        
        try:
            # Initialize Zulip client
            client = zulip.Client(config_file=self.config_file)
            
            # Set up statistics tracking
            last_stats_time = time.time()
            
            def event_handler(event):
                """Handle incoming events"""
                try:
                    # Process the event
                    result = event_processor.process_event(event)
                    
                    # Log processing result
                    if result['success']:
                        logger.debug(
                            f"Processed {result['event_type']} event with "
                            f"{len(result['processed_listeners'])} listeners "
                            f"({result['processing_time_ms']}ms)"
                        )
                    else:
                        logger.warning(
                            f"Failed to process {result['event_type']} event: "
                            f"{len(result['failed_listeners'])} failures"
                        )
                    
                    # Print stats periodically
                    nonlocal last_stats_time
                    if self.stats_interval > 0 and time.time() - last_stats_time > self.stats_interval:
                        self.print_stats()
                        last_stats_time = time.time()
                    
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")
            
            # Start listening
            self.stdout.write("Listening for events...")
            client.call_on_each_event(
                event_handler,
                event_types=self.event_types
            )
            
        except KeyboardInterrupt:
            self.stdout.write("\nShutting down gracefully...")
        except Exception as e:
            logger.error(f"Daemon error: {e}")
            raise CommandError(f"Daemon failed: {e}")
        finally:
            self.cleanup()
    
    def show_registered_listeners(self):
        """Show registered listeners"""
        registered_listeners = event_listener_registry.list_listeners()
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write("REGISTERED EVENT LISTENERS")
        self.stdout.write("="*60)
        
        if not registered_listeners:
            self.stdout.write("No event listeners registered.")
            self.stdout.write("Make sure to:")
            self.stdout.write("1. Import your listener modules")
            self.stdout.write("2. Use @register_event_listener decorator")
            self.stdout.write("3. Set name attribute on your listener class")
            return
        
        for name in registered_listeners:
            handler_class = event_listener_registry.get_handler_class(name)
            description = getattr(handler_class, 'description', 'No description')
            supported_events = getattr(handler_class, 'supported_events', [])
            
            self.stdout.write(f"\n📋 {name}")
            self.stdout.write(f"   Description: {description}")
            self.stdout.write(f"   Events: {', '.join(supported_events) if supported_events else 'All events'}")
            self.stdout.write(f"   Class: {handler_class.__module__}.{handler_class.__name__}")
        
        self.stdout.write("\n" + "="*60)
    
    def run_demo_mode(self):
        """Run in demo mode with sample events"""
        self.stdout.write("\n🚀 Starting Demo Mode")
        self.stdout.write("This will simulate some events to test your listeners.\n")
        
        # Sample events to test
        sample_events = [
            {
                'type': 'message',
                'message': {
                    'id': 12345,
                    'sender_id': 1,
                    'sender_full_name': 'Demo User',
                    'content': 'Hello, this is a test message!',
                    'timestamp': int(time.time()),
                    'recipient_id': 2,
                    'type': 'stream',
                    'stream_id': 1,
                    'subject': 'demo topic'
                },
                'realm_id': 1
            },
            {
                'type': 'presence',
                'user_id': 1,
                'email': 'demo@example.com',
                'presence': {'active': True, 'timestamp': int(time.time())},
                'realm_id': 1
            },
            {
                'type': 'stream',
                'op': 'create',
                'streams': [{
                    'stream_id': 2,
                    'name': 'demo-stream',
                    'description': 'A demo stream for testing',
                }],
                'realm_id': 1
            }
        ]
        
        try:
            for i, event in enumerate(sample_events, 1):
                self.stdout.write(f"\n📨 Processing sample event {i}/{len(sample_events)}: {event['type']}")
                
                # Process the event
                result = event_processor.process_event(event)
                
                # Show results
                if result['success']:
                    self.stdout.write(
                        f"✅ Success: {len(result['processed_listeners'])} listeners processed "
                        f"({result['processing_time_ms']:.1f}ms)"
                    )
                    for listener_name in result['processed_listeners']:
                        self.stdout.write(f"   - {listener_name}")
                else:
                    self.stdout.write(
                        f"❌ Failed: {len(result['failed_listeners'])} listeners failed"
                    )
                    for listener_name, error in result['failed_listeners'].items():
                        self.stdout.write(f"   - {listener_name}: {error}")
                
                # Small delay for readability
                time.sleep(1)
            
            self.stdout.write("\n🎉 Demo completed successfully!")
            self.stdout.write("\nTo run with real Zulip events:")
            self.stdout.write("1. Configure .zuliprc file with your API credentials")
            self.stdout.write("2. Run without --demo-mode flag")
            
        except KeyboardInterrupt:
            self.stdout.write("\n🛑 Demo interrupted by user")
        except Exception as e:
            self.stdout.write(f"\n💥 Demo failed: {e}")
            logger.exception("Demo mode error")
    
    def print_stats(self):
        """Print processing statistics"""
        stats = event_processor.get_stats()
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("Event Processor Statistics")
        self.stdout.write("="*50)
        self.stdout.write(f"Total events processed: {stats['total_events']}")
        self.stdout.write(f"Successful events: {stats['successful_events']}")
        self.stdout.write(f"Failed events: {stats['failed_events']}")
        self.stdout.write(f"Uptime: {stats['uptime_seconds']:.1f} seconds")
        self.stdout.write(f"Active handlers: {stats['active_handlers']}")
        self.stdout.write(f"Registered listeners: {stats['registered_listeners']}")
        
        # Per-listener stats
        listener_stats = ListenerStats.objects.filter(
            listener__enabled=True,
            total_events_processed__gt=0
        ).select_related('listener')
        
        if listener_stats:
            self.stdout.write("\nPer-Listener Statistics:")
            for stat in listener_stats:
                success_rate = (stat.successful_events / stat.total_events_processed) * 100
                self.stdout.write(
                    f"  {stat.listener.name}: "
                    f"{stat.total_events_processed} events, "
                    f"{success_rate:.1f}% success, "
                    f"{stat.average_processing_time_ms:.1f}ms avg"
                )
        
        self.stdout.write("="*50 + "\n")
    
    def cleanup(self):
        """Cleanup when shutting down"""
        self.stdout.write("Cleaning up...")
        event_processor.cleanup()
        self.stdout.write("Event Listener Daemon stopped")