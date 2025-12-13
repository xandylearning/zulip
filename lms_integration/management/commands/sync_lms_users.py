"""
Django management command to sync users from LMS database to Zulip.

This command can be run daily in the morning to sync all users,
or can sync specific users based on IDs.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from lms_integration.lib.user_sync import UserSync
from lms_integration.models import Students, Mentors

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync users from LMS database to Zulip database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--students-only',
            action='store_true',
            help='Sync only students'
        )
        parser.add_argument(
            '--mentors-only',
            action='store_true',
            help='Sync only mentors'
        )
        parser.add_argument(
            '--student-id',
            type=int,
            help='Sync a specific student by ID'
        )
        parser.add_argument(
            '--mentor-id',
            type=int,
            help='Sync a specific mentor by ID'
        )
        parser.add_argument(
            '--realm',
            type=str,
            help='Realm string_id to sync users to (default: first realm)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging'
        )
        parser.add_argument(
            '--sync-batches',
            action='store_true',
            help='Also sync batches and group memberships (adds students/mentors to batch groups)'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        try:
            # Set up logging
            self._setup_logging(options['verbose'])
            
            # Get realm if specified
            realm = None
            if options['realm']:
                from zerver.models import Realm
                try:
                    realm = Realm.objects.get(string_id=options['realm'])
                except Realm.DoesNotExist:
                    raise CommandError(f"Realm '{options['realm']}' not found")
            
            # Initialize user sync
            user_sync = UserSync(realm=realm)
            
            # Handle different sync modes
            if options['student_id']:
                self._sync_single_student(user_sync, options['student_id'])
            elif options['mentor_id']:
                self._sync_single_mentor(user_sync, options['mentor_id'])
            elif options['students_only']:
                self._sync_students(user_sync)
            elif options['mentors_only']:
                self._sync_mentors(user_sync)
            else:
                # Default: sync all users
                if options['sync_batches']:
                    self._sync_all_with_batches(user_sync)
                else:
                    self._sync_all_users(user_sync)
                
        except Exception as e:
            raise CommandError(f'Error running command: {e}')
    
    def _setup_logging(self, verbose: bool):
        """Set up logging configuration."""
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.getLogger('lms_integration').setLevel(level)
    
    def _sync_single_student(self, user_sync: UserSync, student_id: int):
        """Sync a single student."""
        try:
            student = Students.objects.using('lms_db').get(id=student_id)
            created, user_profile, message = user_sync.sync_student(student)
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created user {user_profile.email} from student {student_id}')
                )
            elif user_profile:
                self.stdout.write(
                    self.style.SUCCESS(f'Updated user {user_profile.email} from student {student_id}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Skipped student {student_id}: {message}')
                )
        except Students.DoesNotExist:
            raise CommandError(f'Student {student_id} not found in LMS database')
        except Exception as e:
            raise CommandError(f'Error syncing student {student_id}: {e}')
    
    def _sync_single_mentor(self, user_sync: UserSync, mentor_id: int):
        """Sync a single mentor."""
        try:
            mentor = Mentors.objects.using('lms_db').get(user_id=mentor_id)
            created, user_profile, message = user_sync.sync_mentor(mentor)
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created user {user_profile.email} from mentor {mentor_id}')
                )
            elif user_profile:
                self.stdout.write(
                    self.style.SUCCESS(f'Updated user {user_profile.email} from mentor {mentor_id}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Skipped mentor {mentor_id}: {message}')
                )
        except Mentors.DoesNotExist:
            raise CommandError(f'Mentor {mentor_id} not found in LMS database')
        except Exception as e:
            raise CommandError(f'Error syncing mentor {mentor_id}: {e}')
    
    def _sync_students(self, user_sync: UserSync):
        """Sync all students."""
        self.stdout.write('Syncing all students from LMS to Zulip...')
        stats = user_sync.sync_all_students()
        self._print_stats('Students', stats)
    
    def _sync_mentors(self, user_sync: UserSync):
        """Sync all mentors."""
        self.stdout.write('Syncing all mentors from LMS to Zulip...')
        stats = user_sync.sync_all_mentors()
        self._print_stats('Mentors', stats)
    
    def _sync_all_users(self, user_sync: UserSync):
        """Sync all users (students and mentors)."""
        self.stdout.write('Syncing all users from LMS to Zulip...')
        stats = user_sync.sync_all_users()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('User Sync Summary'))
        self.stdout.write('='*60)
        
        # Students stats
        self._print_stats('Students', stats['students'], indent=2)
        
        # Mentors stats
        self._print_stats('Mentors', stats['mentors'], indent=2)
        
        # Totals
        self.stdout.write('\n' + '-'*60)
        self.stdout.write(f"Total Created: {stats['total_created']}")
        self.stdout.write(f"Total Updated: {stats['total_updated']}")
        self.stdout.write(f"Total Skipped: {stats['total_skipped']}")
        self.stdout.write(f"Total Errors: {stats['total_errors']}")
        self.stdout.write('='*60 + '\n')
    
    def _sync_all_with_batches(self, user_sync: UserSync):
        """Sync all users and batches (with group memberships)."""
        self.stdout.write('Syncing all users and batches from LMS to Zulip...')
        stats = user_sync.sync_all_with_batches()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('Full Sync Summary (Users + Batches)'))
        self.stdout.write('='*60)
        
        # Users stats
        self.stdout.write('\nUsers:')
        self._print_stats('Students', stats['users']['students'], indent=2)
        self._print_stats('Mentors', stats['users']['mentors'], indent=2)
        
        # Batch stats
        self.stdout.write('\nBatches:')
        self.stdout.write(f"  Batches Created: {stats['batches']['batches_created']}")
        self.stdout.write(f"  Batches Updated: {stats['batches']['batches_updated']}")
        self.stdout.write(f"  Students Added to Groups: {stats['batches']['students_added']}")
        self.stdout.write(f"  Mentors Added to Groups: {stats['batches']['mentors_added']}")
        self.stdout.write(f"  Users Removed from Groups: {stats['batches']['users_removed']}")
        if stats['batches']['errors'] > 0:
            self.stdout.write(
                self.style.ERROR(f"  Batch Errors: {stats['batches']['errors']}")
            )
        
        # Totals
        self.stdout.write('\n' + '-'*60)
        self.stdout.write(f"Total Users Created: {stats['total_created']}")
        self.stdout.write(f"Total Users Updated: {stats['total_updated']}")
        self.stdout.write(f"Total Users Skipped: {stats['total_skipped']}")
        self.stdout.write(f"Total Errors: {stats['total_errors']}")
        self.stdout.write('='*60 + '\n')
    
    def _print_stats(self, label: str, stats: dict, indent: int = 0):
        """Print sync statistics."""
        prefix = ' ' * indent
        self.stdout.write(f"\n{prefix}{label}:")
        self.stdout.write(f"{prefix}  Total: {stats['total']}")
        self.stdout.write(f"{prefix}  Created: {stats['created']}")
        self.stdout.write(f"{prefix}  Updated: {stats['updated']}")
        self.stdout.write(f"{prefix}  Skipped: {stats['skipped']}")
        if stats['errors'] > 0:
            self.stdout.write(
                self.style.ERROR(f"{prefix}  Errors: {stats['errors']}")
            )


