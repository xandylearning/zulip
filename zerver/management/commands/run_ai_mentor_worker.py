"""
Management command to run the AI mentor queue worker
"""

from django.core.management.base import BaseCommand

from zerver.worker.ai_mentor_worker import start_ai_mentor_worker


class Command(BaseCommand):
    help = "Run the AI mentor queue worker for processing async AI responses"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Starting AI mentor queue worker...")
        )
        
        try:
            start_ai_mentor_worker()
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("AI mentor worker stopped by user")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"AI mentor worker error: {e}")
            )
            raise
