# General Event Listener Guide for Zulip

## Existing Event Listener Patterns in Zulip

Yes, Zulip has several built-in event listener patterns you can use! Based on the codebase analysis, here are the available approaches:

## 1. **Python Client API Event Listener** (Most Common)

### Location: 
- **API Documentation**: `/Users/straxs/Work/zulip/api_docs/real-time-events.md`
- **Implementation**: Uses `call_on_each_event()` from Zulip Python API

### Basic Usage:

```python
#!/usr/bin/env python3
import zulip

# Initialize client
client = zulip.Client(config_file="~/.zuliprc")

def general_event_handler(event):
    """General event handler that processes all event types"""
    event_type = event.get('type')
    
    print(f"Received event: {event_type}")
    
    # Handle different event types
    if event_type == 'message':
        handle_message_event(event)
    elif event_type == 'presence':
        handle_presence_event(event)
    elif event_type == 'typing':
        handle_typing_event(event)
    elif event_type == 'reaction':
        handle_reaction_event(event)
    elif event_type == 'update_message':
        handle_message_update_event(event)
    elif event_type == 'delete_message':
        handle_message_delete_event(event)
    elif event_type == 'subscription':
        handle_subscription_event(event)
    elif event_type == 'stream':
        handle_stream_event(event)
    else:
        handle_unknown_event(event)

def handle_message_event(event):
    message = event['message']
    print(f"New message from {message['sender_full_name']}: {message['content']}")

def handle_presence_event(event):
    print(f"User presence update: {event}")

def handle_typing_event(event):
    print(f"Typing notification: {event}")

def handle_reaction_event(event):
    print(f"Reaction event: {event}")

def handle_message_update_event(event):
    print(f"Message updated: {event}")

def handle_message_delete_event(event):
    print(f"Message deleted: {event}")

def handle_subscription_event(event):
    print(f"Subscription change: {event}")

def handle_stream_event(event):
    print(f"Stream event: {event}")

def handle_unknown_event(event):
    print(f"Unknown event type: {event}")

# Start listening to all events
print("Starting general event listener...")
client.call_on_each_event(general_event_handler)
```

### Advanced Usage with Filtering:

```python
#!/usr/bin/env python3
import zulip

client = zulip.Client(config_file="~/.zuliprc")

def filtered_event_handler(event):
    """Event handler with filtering capabilities"""
    event_type = event.get('type')
    
    # Log all events
    print(f"Event: {event_type} - {event.get('id', 'no-id')}")
    
    # Your custom logic here
    process_event(event)

def process_event(event):
    """Process events based on your requirements"""
    # Add your custom event processing logic
    pass

# Listen for specific event types only
client.call_on_each_event(
    filtered_event_handler,
    event_types=['message', 'presence', 'typing', 'reaction']
)
```

## 2. **Django Management Command Event Listener**

### Create a Custom Management Command:

```python
# File: zerver/management/commands/general_event_listener.py

import logging
from typing import Any, Dict
from django.core.management.base import BaseCommand
import zulip

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'General Event Listener for Zulip'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--config-file',
            type=str,
            default='~/.zuliprc',
            help='Path to Zulip configuration file'
        )
        parser.add_argument(
            '--event-types',
            nargs='+',
            help='Specific event types to listen for'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging'
        )
    
    def handle(self, *args, **options):
        # Set up logging
        if options['verbose']:
            logging.basicConfig(level=logging.INFO)
        
        self.stdout.write('Starting General Event Listener...')
        
        # Initialize Zulip client
        client = zulip.Client(config_file=options['config_file'])
        
        # Set up event handler
        event_handler = GeneralEventHandler(self.stdout)
        
        # Determine event types to listen for
        event_types = options.get('event_types')
        if event_types:
            self.stdout.write(f'Listening for events: {", ".join(event_types)}')
        else:
            self.stdout.write('Listening for all events')
        
        # Start listening
        try:
            client.call_on_each_event(
                event_handler.handle_event,
                event_types=event_types
            )
        except KeyboardInterrupt:
            self.stdout.write('Event listener stopped by user')
        except Exception as e:
            self.stderr.write(f'Error in event listener: {e}')
            logger.exception('Event listener error')


class GeneralEventHandler:
    """General event handler class"""
    
    def __init__(self, stdout):
        self.stdout = stdout
        self.event_count = 0
        
        # Event type handlers
        self.handlers = {
            'message': self.handle_message,
            'presence': self.handle_presence,
            'typing': self.handle_typing,
            'reaction': self.handle_reaction,
            'update_message': self.handle_update_message,
            'delete_message': self.handle_delete_message,
            'submission': self.handle_submessage,
            'subscription': self.handle_subscription,
            'stream': self.handle_stream,
            'user_status': self.handle_user_status,
            'realm_user': self.handle_realm_user,
            'alert_words': self.handle_alert_words,
            'custom_profile_fields': self.handle_custom_profile_fields,
            'heartbeat': self.handle_heartbeat,
        }
    
    def handle_event(self, event: Dict[str, Any]) -> None:
        """Main event handler"""
        self.event_count += 1
        event_type = event.get('type', 'unknown')
        
        # Log the event
        self.stdout.write(f"Event #{self.event_count}: {event_type}")
        
        # Call specific handler
        handler = self.handlers.get(event_type, self.handle_unknown)
        try:
            handler(event)
        except Exception as e:
            logger.error(f"Error handling {event_type} event: {e}")
    
    def handle_message(self, event: Dict[str, Any]) -> None:
        """Handle message events"""
        message = event['message']
        self.stdout.write(
            f"  Message from {message['sender_full_name']}: "
            f"{message['content'][:50]}..."
        )
    
    def handle_presence(self, event: Dict[str, Any]) -> None:
        """Handle presence events"""
        self.stdout.write(f"  Presence update: {event.get('user_id')}")
    
    def handle_typing(self, event: Dict[str, Any]) -> None:
        """Handle typing events"""
        sender = event.get('sender', {})
        self.stdout.write(f"  Typing: {sender.get('user_id')} - {event.get('op')}")
    
    def handle_reaction(self, event: Dict[str, Any]) -> None:
        """Handle reaction events"""
        self.stdout.write(
            f"  Reaction {event.get('op')}: {event.get('emoji_name')} "
            f"on message {event.get('message_id')}"
        )
    
    def handle_update_message(self, event: Dict[str, Any]) -> None:
        """Handle message update events"""
        self.stdout.write(f"  Message updated: {event.get('message_id')}")
    
    def handle_delete_message(self, event: Dict[str, Any]) -> None:
        """Handle message delete events"""
        self.stdout.write(f"  Messages deleted: {event.get('message_ids')}")
    
    def handle_submessage(self, event: Dict[str, Any]) -> None:
        """Handle submessage events"""
        self.stdout.write(f"  Submessage: {event.get('message_id')}")
    
    def handle_subscription(self, event: Dict[str, Any]) -> None:
        """Handle subscription events"""
        self.stdout.write(f"  Subscription {event.get('op')}")
    
    def handle_stream(self, event: Dict[str, Any]) -> None:
        """Handle stream events"""
        self.stdout.write(f"  Stream {event.get('op')}: {event.get('name', 'unknown')}")
    
    def handle_user_status(self, event: Dict[str, Any]) -> None:
        """Handle user status events"""
        self.stdout.write(f"  User status: {event.get('user_id')}")
    
    def handle_realm_user(self, event: Dict[str, Any]) -> None:
        """Handle realm user events"""
        self.stdout.write(f"  Realm user {event.get('op')}")
    
    def handle_alert_words(self, event: Dict[str, Any]) -> None:
        """Handle alert words events"""
        self.stdout.write("  Alert words updated")
    
    def handle_custom_profile_fields(self, event: Dict[str, Any]) -> None:
        """Handle custom profile fields events"""
        self.stdout.write("  Custom profile fields updated")
    
    def handle_heartbeat(self, event: Dict[str, Any]) -> None:
        """Handle heartbeat events"""
        self.stdout.write("  Heartbeat")
    
    def handle_unknown(self, event: Dict[str, Any]) -> None:
        """Handle unknown event types"""
        self.stdout.write(f"  Unknown event type: {event.get('type')}")
```

### Usage:

```bash
# Listen to all events
python manage.py general_event_listener --verbose

# Listen to specific event types
python manage.py general_event_listener --event-types message presence typing

# Use custom config file
python manage.py general_event_listener --config-file /path/to/zuliprc
```

## 3. **Advanced Event Listener with Queue Processing**

### Create a Queue-Based Event Processor:

```python
# File: zerver/management/commands/advanced_event_listener.py

import asyncio
import json
import logging
import queue
import threading
from typing import Any, Dict
from django.core.management.base import BaseCommand
import zulip

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Advanced Event Listener with Queue Processing'
    
    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=2, help='Number of worker threads')
        parser.add_argument('--queue-size', type=int, default=1000, help='Event queue size')
    
    def handle(self, *args, **options):
        listener = AdvancedEventListener(
            workers=options['workers'],
            queue_size=options['queue_size']
        )
        listener.start()


class AdvancedEventListener:
    """Advanced event listener with multi-threaded processing"""
    
    def __init__(self, workers=2, queue_size=1000):
        self.workers = workers
        self.event_queue = queue.Queue(maxsize=queue_size)
        self.stop_event = threading.Event()
        self.worker_threads = []
        
    def start(self):
        """Start the event listener and workers"""
        print(f"Starting {self.workers} worker threads...")
        
        # Start worker threads
        for i in range(self.workers):
            worker = threading.Thread(target=self.worker, args=(i,))
            worker.daemon = True
            worker.start()
            self.worker_threads.append(worker)
        
        # Start event listener
        print("Starting event listener...")
        client = zulip.Client(config_file="~/.zuliprc")
        
        try:
            client.call_on_each_event(self.enqueue_event)
        except KeyboardInterrupt:
            print("Stopping event listener...")
            self.stop_event.set()
    
    def enqueue_event(self, event: Dict[str, Any]) -> None:
        """Add event to processing queue"""
        try:
            self.event_queue.put(event, timeout=1)
        except queue.Full:
            logger.warning("Event queue full, dropping event")
    
    def worker(self, worker_id: int) -> None:
        """Worker thread for processing events"""
        print(f"Worker {worker_id} started")
        
        while not self.stop_event.is_set():
            try:
                event = self.event_queue.get(timeout=1)
                self.process_event(event, worker_id)
                self.event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        print(f"Worker {worker_id} stopped")
    
    def process_event(self, event: Dict[str, Any], worker_id: int) -> None:
        """Process individual events"""
        event_type = event.get('type')
        print(f"Worker {worker_id} processing {event_type}")
        
        # Add your custom event processing logic here
        if event_type == 'message':
            self.process_message_event(event)
        elif event_type == 'presence':
            self.process_presence_event(event)
        # Add more event type handlers as needed
    
    def process_message_event(self, event: Dict[str, Any]) -> None:
        """Process message events"""
        message = event['message']
        # Your custom message processing logic
        pass
    
    def process_presence_event(self, event: Dict[str, Any]) -> None:
        """Process presence events"""
        # Your custom presence processing logic
        pass
```

## 4. **Backend Integration Event Listener**

### Hook into Zulip's Event System Directly:

```python
# File: zerver/lib/custom_event_processor.py

from typing import Any, Dict, List
from zerver.tornado.event_queue import process_notification
from zerver.models import UserProfile
from zerver.lib.events import fetch_initial_state_data
import logging

logger = logging.getLogger(__name__)

class CustomEventProcessor:
    """Custom event processor that hooks into Zulip's event system"""
    
    def __init__(self):
        self.event_handlers = {
            'message': self.handle_message_event,
            'presence': self.handle_presence_event,
            'typing': self.handle_typing_event,
            'reaction': self.handle_reaction_event,
            'update_message': self.handle_update_message_event,
            'delete_message': self.handle_delete_message_event,
        }
    
    def register_event_handler(self, event_type: str, handler):
        """Register a custom event handler"""
        self.event_handlers[event_type] = handler
    
    def process_notification(self, notice: Dict[str, Any]) -> None:
        """Process event notifications from Zulip's event system"""
        event = notice.get('event', {})
        users = notice.get('users', [])
        event_type = event.get('type')
        
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type](event, users)
            except Exception as e:
                logger.error(f"Error processing {event_type} event: {e}")
        else:
            self.handle_unknown_event(event, users)
    
    def handle_message_event(self, event: Dict[str, Any], users: List[int]) -> None:
        """Handle message events"""
        message = event.get('message', {})
        logger.info(f"Message event: {message.get('id')} to {len(users)} users")
        # Your custom logic here
    
    def handle_presence_event(self, event: Dict[str, Any], users: List[int]) -> None:
        """Handle presence events"""
        logger.info(f"Presence event for user {event.get('user_id')}")
        # Your custom logic here
    
    def handle_typing_event(self, event: Dict[str, Any], users: List[int]) -> None:
        """Handle typing events"""
        sender = event.get('sender', {})
        logger.info(f"Typing event from user {sender.get('user_id')}")
        # Your custom logic here
    
    def handle_reaction_event(self, event: Dict[str, Any], users: List[int]) -> None:
        """Handle reaction events"""
        logger.info(f"Reaction {event.get('op')} on message {event.get('message_id')}")
        # Your custom logic here
    
    def handle_update_message_event(self, event: Dict[str, Any], users: List[int]) -> None:
        """Handle message update events"""
        logger.info(f"Message update: {event.get('message_id')}")
        # Your custom logic here
    
    def handle_delete_message_event(self, event: Dict[str, Any], users: List[int]) -> None:
        """Handle message delete events"""
        logger.info(f"Message delete: {event.get('message_ids')}")
        # Your custom logic here
    
    def handle_unknown_event(self, event: Dict[str, Any], users: List[int]) -> None:
        """Handle unknown events"""
        logger.info(f"Unknown event type: {event.get('type')}")

# Global instance
custom_processor = CustomEventProcessor()
```

## 5. **Event Listener Service (Production Ready)**

### Create a Complete Service:

```python
# File: scripts/event_listener_service.py

#!/usr/bin/env python3

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.settings')
django.setup()

import zulip
from zerver.models import UserProfile, Realm

class EventListenerService:
    """Production-ready event listener service"""
    
    def __init__(self, config_file=None, log_file=None, event_types=None):
        self.config_file = config_file or "~/.zuliprc"
        self.log_file = log_file
        self.event_types = event_types
        self.running = True
        self.stats = {
            'events_processed': 0,
            'start_time': datetime.now(),
            'last_event_time': None,
        }
        
        # Setup logging
        self.setup_logging()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        if self.log_file:
            logging.basicConfig(
                level=logging.INFO,
                format=log_format,
                handlers=[
                    logging.FileHandler(self.log_file),
                    logging.StreamHandler(sys.stdout)
                ]
            )
        else:
            logging.basicConfig(level=logging.INFO, format=log_format)
        
        self.logger = logging.getLogger(__name__)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        self.print_stats()
        sys.exit(0)
    
    def print_stats(self):
        """Print service statistics"""
        uptime = datetime.now() - self.stats['start_time']
        self.logger.info(f"Service Statistics:")
        self.logger.info(f"  Events processed: {self.stats['events_processed']}")
        self.logger.info(f"  Uptime: {uptime}")
        self.logger.info(f"  Last event: {self.stats['last_event_time']}")
    
    def event_handler(self, event):
        """Main event handler"""
        if not self.running:
            return
        
        self.stats['events_processed'] += 1
        self.stats['last_event_time'] = datetime.now()
        
        event_type = event.get('type', 'unknown')
        self.logger.debug(f"Processing event: {event_type}")
        
        try:
            # Process the event
            self.process_event(event)
            
            # Log stats every 100 events
            if self.stats['events_processed'] % 100 == 0:
                self.logger.info(f"Processed {self.stats['events_processed']} events")
        
        except Exception as e:
            self.logger.error(f"Error processing event {event_type}: {e}")
    
    def process_event(self, event):
        """Process individual events - override this method"""
        event_type = event.get('type')
        
        # Add your custom event processing logic here
        if event_type == 'message':
            self.process_message(event)
        elif event_type == 'presence':
            self.process_presence(event)
        elif event_type == 'typing':
            self.process_typing(event)
        # Add more event types as needed
    
    def process_message(self, event):
        """Process message events - customize as needed"""
        message = event['message']
        self.logger.info(f"Message from {message['sender_full_name']}: {message['content'][:50]}...")
    
    def process_presence(self, event):
        """Process presence events - customize as needed"""
        self.logger.info(f"Presence update for user {event.get('user_id')}")
    
    def process_typing(self, event):
        """Process typing events - customize as needed"""
        sender = event.get('sender', {})
        self.logger.info(f"Typing from user {sender.get('user_id')}")
    
    def start(self):
        """Start the event listener service"""
        self.logger.info("Starting Event Listener Service...")
        self.logger.info(f"Config file: {self.config_file}")
        self.logger.info(f"Event types: {self.event_types or 'all'}")
        
        try:
            # Initialize Zulip client
            client = zulip.Client(config_file=self.config_file)
            
            # Test connection
            result = client.get_profile()
            if result['result'] == 'success':
                self.logger.info(f"Connected as: {result['full_name']} ({result['email']})")
            else:
                self.logger.error(f"Connection failed: {result}")
                return
            
            # Start listening for events
            self.logger.info("Listening for events...")
            client.call_on_each_event(
                self.event_handler,
                event_types=self.event_types
            )
            
        except Exception as e:
            self.logger.error(f"Service error: {e}")
        finally:
            self.logger.info("Event Listener Service stopped")


def main():
    parser = argparse.ArgumentParser(description='Zulip Event Listener Service')
    parser.add_argument('--config', help='Zulip config file path')
    parser.add_argument('--log-file', help='Log file path')
    parser.add_argument('--event-types', nargs='+', help='Event types to listen for')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    # Create and start service
    service = EventListenerService(
        config_file=args.config,
        log_file=args.log_file,
        event_types=args.event_types
    )
    
    if args.daemon:
        # TODO: Add proper daemon implementation
        pass
    
    service.start()

if __name__ == "__main__":
    main()
```

### Usage:

```bash
# Basic usage
python scripts/event_listener_service.py

# With specific event types
python scripts/event_listener_service.py --event-types message presence typing

# With logging
python scripts/event_listener_service.py --log-file /var/log/zulip-events.log

# Run in background
nohup python scripts/event_listener_service.py --log-file events.log > /dev/null 2>&1 &
```

## Key Event Types Available

Based on the codebase analysis, here are the main event types you can listen for:

### Message-Related Events:
- `message` - New messages
- `update_message` - Message edits
- `delete_message` - Message deletions
- `update_message_flags` - Read/unread, starred, etc.
- `submessage` - Widget interactions

### User-Related Events:
- `presence` - User online/offline status
- `typing` - Typing indicators
- `user_status` - Status/emoji changes
- `realm_user` - User additions/removals/updates

### Stream/Channel Events:
- `stream` - Channel creation/updates/deletion
- `subscription` - Subscription changes

### Other Events:
- `reaction` - Emoji reactions
- `alert_words` - Alert word matches
- `heartbeat` - Keep-alive events
- `custom_profile_fields` - Profile updates
- `realm` - Organization settings changes

## Configuration

### Create Bot User:

```bash
# In Django shell
python manage.py shell

from zerver.models import UserProfile, Realm
from zerver.actions.users import do_create_user

realm = Realm.objects.get(string_id='your-realm')
bot = do_create_user(
    email='event-listener-bot@example.com',
    password=None,
    realm=realm,
    full_name='Event Listener Bot',
    bot_type=UserProfile.DEFAULT_BOT,
    is_bot=True
)
```

### Create Configuration File:

```bash
# ~/.zuliprc
[api]
email=event-listener-bot@example.com
key=your-bot-api-key
site=https://your-zulip-server.com
```

## Deployment Options

### 1. Systemd Service:

```ini
# /etc/systemd/system/zulip-event-listener.service
[Unit]
Description=Zulip Event Listener Service
After=network.target

[Service]
Type=simple
User=zulip
WorkingDirectory=/home/zulip/deployments/current
Environment=DJANGO_SETTINGS_MODULE=zproject.prod_settings
ExecStart=/home/zulip/deployments/current/scripts/event_listener_service.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 2. Docker Service:

```dockerfile
# Add to docker-compose.yml
services:
  event-listener:
    build: .
    command: python scripts/event_listener_service.py
    environment:
      - DJANGO_SETTINGS_MODULE=zproject.settings
    volumes:
      - .:/app
    restart: unless-stopped
```

The general event listener system in Zulip is very flexible and can handle all the event types you need for your AI mentoring system or any other custom application!