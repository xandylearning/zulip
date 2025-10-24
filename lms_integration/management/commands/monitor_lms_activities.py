"""
Django management command to monitor LMS activities.

This command polls the LMS database for new student activities and creates
events for processing by the event listener system.
"""

import logging
import signal
import sys
import time
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection

from lms_integration.lib.activity_monitor import ActivityMonitor
from lms_integration.event_listeners import LMSActivityEventHandler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor LMS database for new student activities and create events'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor = None
        self.event_handler = None
        self.running = False
        self.shutdown_requested = False
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Polling interval in seconds (default: 60)'
        )
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run as daemon (continuous monitoring)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit'
        )
        parser.add_argument(
            '--process-pending',
            action='store_true',
            help='Process pending events and exit'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show event statistics and exit'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        try:
            # Set up logging
            self._setup_logging(options['verbose'])
            
            # Check if monitoring is enabled
            if not getattr(settings, 'LMS_ACTIVITY_MONITOR_ENABLED', False):
                self.stdout.write(
                    self.style.WARNING('LMS activity monitoring is disabled in settings')
                )
                return
            
            # Initialize components
            self._initialize_components(options)
            
            # Handle different command modes
            if options['stats']:
                self._show_stats()
            elif options['process_pending']:
                self._process_pending_events()
            elif options['once']:
                self._run_once()
            elif options['daemon']:
                self._run_daemon(options['interval'])
            else:
                # Default: run once
                self._run_once()
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nShutdown requested by user'))
        except Exception as e:
            raise CommandError(f'Error running command: {e}')
        finally:
            self._cleanup()
    
    def _setup_logging(self, verbose: bool):
        """Set up logging configuration."""
        level = logging.DEBUG if verbose else logging.INFO
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Set specific logger levels
        logging.getLogger('lms_integration').setLevel(level)
        logging.getLogger('django.db').setLevel(logging.WARNING)
    
    def _initialize_components(self, options):
        """Initialize monitoring components."""
        try:
            # Initialize activity monitor
            poll_interval = options.get('interval', 60)
            self.monitor = ActivityMonitor(poll_interval=poll_interval)
            
            # Initialize event handler
            self.event_handler = LMSActivityEventHandler()
            
            self.stdout.write(
                self.style.SUCCESS('LMS activity monitoring components initialized')
            )
            
        except Exception as e:
            raise CommandError(f'Failed to initialize components: {e}')
    
    def _show_stats(self):
        """Show event statistics."""
        try:
            stats = self.event_handler.get_event_stats()
            
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS('LMS Activity Event Statistics'))
            self.stdout.write('='*50)
            self.stdout.write(f"Total Events: {stats['total_events']}")
            self.stdout.write(f"Processed Events: {stats['processed_events']}")
            self.stdout.write(f"Pending Events: {stats['pending_events']}")
            self.stdout.write(f"Events with Notifications: {stats['events_with_notifications']}")
            self.stdout.write(f"Events with Errors: {stats['events_with_errors']}")
            self.stdout.write('='*50 + '\n')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error getting statistics: {e}')
            )
    
    def _process_pending_events(self):
        """Process all pending events."""
        try:
            self.stdout.write('Processing pending LMS activity events...')
            
            processed_count = self.event_handler.process_pending_events()
            
            self.stdout.write(
                self.style.SUCCESS(f'Processed {processed_count} pending events')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error processing pending events: {e}')
            )
    
    def _run_once(self):
        """Run monitoring once and exit."""
        try:
            self.stdout.write('Running LMS activity monitor (once)...')
            
            events_created = self.monitor.process_activities()
            
            if events_created > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Created {events_created} new activity events')
                )
                
                # Process the new events
                processed_count = self.event_handler.process_pending_events()
                self.stdout.write(
                    self.style.SUCCESS(f'Processed {processed_count} events')
                )
            else:
                self.stdout.write('No new activities detected')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error in single run: {e}')
            )
    
    def _run_daemon(self, interval: int):
        """Run monitoring as daemon."""
        self.stdout.write(f'Starting LMS activity monitor daemon (interval: {interval}s)')
        self.stdout.write('Press Ctrl+C to stop')
        
        self.running = True
        
        try:
            while self.running and not self.shutdown_requested:
                try:
                    # Process activities
                    events_created = self.monitor.process_activities()
                    
                    if events_created > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f'Created {events_created} new activity events')
                        )
                        
                        # Process the new events
                        processed_count = self.event_handler.process_pending_events()
                        if processed_count > 0:
                            self.stdout.write(
                                self.style.SUCCESS(f'Processed {processed_count} events')
                            )
                    
                    # Wait for next poll
                    if self.running:
                        time.sleep(interval)
                        
                except Exception as e:
                    logger.error(f'Error in daemon loop: {e}')
                    self.stdout.write(
                        self.style.ERROR(f'Error in monitoring loop: {e}')
                    )
                    # Continue running despite errors
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nShutdown requested'))
        finally:
            self.running = False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.stdout.write(self.style.WARNING(f'\nReceived signal {signum}, shutting down...'))
        self.shutdown_requested = True
        self.running = False
    
    def _cleanup(self):
        """Clean up resources."""
        try:
            # Close database connections
            connection.close()
            self.stdout.write('Cleanup completed')
        except Exception as e:
            logger.error(f'Error during cleanup: {e}')
