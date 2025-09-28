"""
AI Mentor Queue Worker

This worker processes AI mentor responses asynchronously using a simple
polling approach that works with Zulip's existing infrastructure.
"""

import logging
import time
from typing import Any, Dict

from zerver.actions.ai_mentor_events import send_async_ai_response
from zerver.lib.queue import get_queue_client

logger = logging.getLogger(__name__)


class AIMentorWorker:
    """
    Worker for processing AI mentor responses and AI agent conversations asynchronously
    """
    
    def __init__(self) -> None:
        self.queue_name = "ai_mentor_responses"
        self.running = False
    
    def process_ai_mentor_event(self, event: Dict[str, Any]) -> None:
        """
        Process AI mentor response events from the queue
        """
        try:
            event_type = event.get("type")
            
            if event_type == "send_ai_response":
                logger.info(f"Processing async AI response: mentor={event.get('mentor_id')}, student={event.get('student_id')}")
                send_async_ai_response(event)
            elif event_type == "ai_agent_conversation":
                logger.info(f"Processing AI agent conversation: {event.get('event_data', {}).get('mentor', {}).get('user_id')}")
                
                # Extract the actual event data
                event_data = event.get("event_data", {})
                
                # Dispatch to AI agent event listener for processing
                from zerver.event_listeners.ai_mentor import handle_ai_agent_conversation
                handle_ai_agent_conversation(event_data)
            else:
                logger.warning(f"Unknown AI mentor event type: {event_type}")
                
        except Exception as e:
            logger.error(f"Error processing AI mentor event: {e}", exc_info=True)
    
    
    def start(self) -> None:
        """Start the AI mentor worker with JSON consumer for the unified queue"""
        if self.running:
            logger.warning("AI mentor worker is already running")
            return
            
        logger.info("Starting AI mentor queue worker for unified queue")
        self.running = True
        
        try:
            queue_client = get_queue_client()
            
            def process_batch(events: list[dict[str, Any]]) -> None:
                """Process a batch of AI mentor events (both responses and conversations)"""
                for event in events:
                    try:
                        logger.info(f"Processing AI mentor event: {event}")
                        self.process_ai_mentor_event(event)
                    except Exception as e:
                        logger.error(f"Error processing event: {e}")
            
            # Start the JSON consumer for the unified queue
            queue_client.start_json_consumer(
                queue_name=self.queue_name,
                callback=process_batch,
                batch_size=1,
                timeout=None
            )
            
            logger.info("AI mentor queue worker started successfully")
            
            # Keep the worker running
            while self.running:
                time.sleep(1)
                    
        except KeyboardInterrupt:
            logger.info("AI mentor worker stopped by user")
        except Exception as e:
            logger.error(f"AI mentor worker error: {e}")
        finally:
            self.running = False
            logger.info("AI mentor queue worker stopped")
    
    def stop(self) -> None:
        """Stop the AI mentor worker"""
        if not self.running:
            logger.warning("AI mentor worker is not running")
            return
            
        logger.info("Stopping AI mentor queue worker")
        self.running = False


# Global worker instance
ai_mentor_worker = AIMentorWorker()


def start_ai_mentor_worker() -> None:
    """Start the AI mentor worker (called by supervisor)"""
    ai_mentor_worker.start()


def stop_ai_mentor_worker() -> None:
    """Stop the AI mentor worker (called by supervisor)"""
    ai_mentor_worker.stop()