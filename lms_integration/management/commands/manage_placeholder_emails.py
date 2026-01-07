"""
Management command for handling placeholder emails in LMS integration.

This command provides utilities for:
- Converting existing LMS users without emails to use placeholder emails
- Updating placeholder emails to real emails when available
- Reporting on placeholder email usage
- Cleaning up placeholder emails
"""

import sys
from typing import Any, List, Dict, Optional
from argparse import ArgumentParser

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from zerver.models import UserProfile, Realm
from lms_integration.models import Students, Mentors
from lms_integration.lib.email_utils import (
    validate_and_prepare_email,
    update_email_if_changed,
    is_placeholder_email,
    generate_placeholder_email,
    get_placeholder_email_stats,
)


class Command(BaseCommand):
    help = "Manage placeholder emails for LMS integration users"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            '--realm',
            type=str,
            help='Realm string ID to operate on (default: first realm)'
        )

        subparsers = parser.add_subparsers(
            dest='action',
            help='Action to perform',
            required=True
        )

        # Report action
        report_parser = subparsers.add_parser(
            'report',
            help='Generate a report of placeholder email usage'
        )
        report_parser.add_argument(
            '--format',
            choices=['text', 'json', 'csv'],
            default='text',
            help='Output format for the report'
        )

        # Convert action
        convert_parser = subparsers.add_parser(
            'convert',
            help='Convert existing users without emails to placeholder emails'
        )
        convert_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        convert_parser.add_argument(
            '--domain',
            type=str,
            help='Domain to use for placeholder emails (default: from settings)'
        )

        # Update action
        update_parser = subparsers.add_parser(
            'update',
            help='Update placeholder emails to real emails from LMS'
        )
        update_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

        # Bulk update action
        bulk_update_parser = subparsers.add_parser(
            'bulk-update',
            help='Bulk update emails from a CSV file'
        )
        bulk_update_parser.add_argument(
            'csv_file',
            help='CSV file with username,email pairs'
        )
        bulk_update_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

        # Clean action
        clean_parser = subparsers.add_parser(
            'clean',
            help='Clean up placeholder emails (convert back to real emails where possible)'
        )
        clean_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Main command handler."""
        self.verbosity = options.get('verbosity', 1)

        # Get realm
        self.realm = self.get_realm(options.get('realm'))
        if not self.realm:
            raise CommandError("No realm found. Please specify --realm or ensure at least one realm exists.")

        # Dispatch to action handlers
        action = options['action']
        if action == 'report':
            self.handle_report(options)
        elif action == 'convert':
            self.handle_convert(options)
        elif action == 'update':
            self.handle_update(options)
        elif action == 'bulk-update':
            self.handle_bulk_update(options)
        elif action == 'clean':
            self.handle_clean(options)
        else:
            raise CommandError(f"Unknown action: {action}")

    def get_realm(self, realm_string_id: Optional[str]) -> Optional[Realm]:
        """Get realm by string ID or return first realm."""
        if realm_string_id:
            try:
                return Realm.objects.get(string_id=realm_string_id)
            except Realm.DoesNotExist:
                raise CommandError(f"Realm '{realm_string_id}' not found")

        # Return first realm
        return Realm.objects.first()

    def handle_report(self, options: Dict[str, Any]) -> None:
        """Generate a report of placeholder email usage."""
        stats = get_placeholder_email_stats(self.realm)

        format_type = options['format']

        if format_type == 'json':
            import json
            self.stdout.write(json.dumps(stats, indent=2))
        elif format_type == 'csv':
            self.stdout.write("metric,value")
            for key, value in stats.items():
                self.stdout.write(f"{key},{value}")
        else:  # text format
            self.stdout.write(f"Placeholder Email Report for {self.realm.string_id}")
            self.stdout.write("=" * 50)
            self.stdout.write(f"Total Users: {stats['total_users']}")
            self.stdout.write(f"Users with Real Emails: {stats['real_email_users']}")
            self.stdout.write(f"Users with Placeholder Emails: {stats['placeholder_users']}")
            self.stdout.write(f"Placeholder Percentage: {stats['placeholder_percentage']}%")

    def handle_convert(self, options: Dict[str, Any]) -> None:
        """Convert existing users without emails to placeholder emails."""
        dry_run = options['dry_run']
        domain = options.get('domain')

        if dry_run:
            self.stdout.write("DRY RUN: No changes will be made")

        # This action is primarily for historical purposes since new
        # user sync now automatically handles users without emails
        self.stdout.write(self.style.WARNING(
            "Note: New LMS user sync automatically handles users without emails. "
            "This command is mainly for historical data cleanup."
        ))

        converted = 0
        errors = 0

        # Find users in LMS that might need conversion
        for student in Students.objects.using('lms_db').filter(is_active=True):
            if not student.email:  # Student has no email in LMS
                try:
                    # Check if user exists in Zulip but has some invalid/missing email
                    # This is mainly for cleanup of edge cases
                    if not dry_run:
                        # The actual conversion would happen during next sync
                        # This is more of a report of what would be converted
                        pass

                    if self.verbosity >= 2:
                        placeholder_email = generate_placeholder_email(
                            student.username,
                            domain
                        )
                        self.stdout.write(
                            f"Would convert student {student.username} -> {placeholder_email}"
                        )
                    converted += 1

                except Exception as e:
                    self.stderr.write(f"Error processing student {student.id}: {e}")
                    errors += 1

        self.stdout.write(f"Conversion summary:")
        self.stdout.write(f"  Students that would use placeholder emails: {converted}")
        if errors > 0:
            self.stdout.write(f"  Errors encountered: {errors}")

        if not dry_run and converted == 0:
            self.stdout.write("No conversions needed. Run user sync to create users with placeholder emails.")

    def handle_update(self, options: Dict[str, Any]) -> None:
        """Update placeholder emails to real emails from LMS."""
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write("DRY RUN: No changes will be made")

        updated = 0
        errors = 0

        # Get all users with placeholder emails
        placeholder_users = UserProfile.objects.filter(
            realm=self.realm,
            is_active=True
        )

        for user in placeholder_users:
            if not is_placeholder_email(user.delivery_email):
                continue

            try:
                # Extract username from placeholder email to find LMS record
                username = user.delivery_email.split('@')[0]

                # Look for student first
                try:
                    student = Students.objects.using('lms_db').get(username=username)
                    if student.email:
                        if not dry_run:
                            updated_email = update_email_if_changed(user, student.email, username)
                            if updated_email:
                                updated += 1
                                if self.verbosity >= 2:
                                    self.stdout.write(f"Updated {username}: {user.delivery_email} -> {student.email}")
                        else:
                            if self.verbosity >= 2:
                                self.stdout.write(f"Would update {username}: {user.delivery_email} -> {student.email}")
                            updated += 1
                        continue
                except Students.DoesNotExist:
                    pass

                # Look for mentor
                try:
                    mentor = Mentors.objects.using('lms_db').get(username=username)
                    if mentor.email:
                        if not dry_run:
                            updated_email = update_email_if_changed(user, mentor.email, username)
                            if updated_email:
                                updated += 1
                                if self.verbosity >= 2:
                                    self.stdout.write(f"Updated {username}: {user.delivery_email} -> {mentor.email}")
                        else:
                            if self.verbosity >= 2:
                                self.stdout.write(f"Would update {username}: {user.delivery_email} -> {mentor.email}")
                            updated += 1
                except Mentors.DoesNotExist:
                    pass

            except Exception as e:
                self.stderr.write(f"Error updating user {user.delivery_email}: {e}")
                errors += 1

        self.stdout.write(f"Update summary:")
        self.stdout.write(f"  Users updated: {updated}")
        if errors > 0:
            self.stdout.write(f"  Errors encountered: {errors}")

    def handle_bulk_update(self, options: Dict[str, Any]) -> None:
        """Bulk update emails from a CSV file."""
        csv_file = options['csv_file']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write("DRY RUN: No changes will be made")

        try:
            import csv

            updated = 0
            errors = 0

            with open(csv_file, 'r') as f:
                reader = csv.reader(f)
                for row_num, row in enumerate(reader, 1):
                    if len(row) < 2:
                        self.stderr.write(f"Row {row_num}: Invalid format (need username,email)")
                        errors += 1
                        continue

                    username, email = row[0].strip(), row[1].strip()

                    if not username or not email:
                        self.stderr.write(f"Row {row_num}: Empty username or email")
                        errors += 1
                        continue

                    # Validate email
                    try:
                        validate_email(email)
                    except ValidationError:
                        self.stderr.write(f"Row {row_num}: Invalid email format: {email}")
                        errors += 1
                        continue

                    try:
                        # Find user with placeholder email based on username
                        placeholder_email = generate_placeholder_email(username)

                        user = UserProfile.objects.get(
                            realm=self.realm,
                            delivery_email__iexact=placeholder_email
                        )

                        if not dry_run:
                            # Update email
                            user.delivery_email = email
                            user.email = email
                            user.save(update_fields=['delivery_email', 'email'])

                        updated += 1
                        if self.verbosity >= 2:
                            action = "Would update" if dry_run else "Updated"
                            self.stdout.write(f"{action} {username}: {placeholder_email} -> {email}")

                    except UserProfile.DoesNotExist:
                        self.stderr.write(f"Row {row_num}: User not found for username: {username}")
                        errors += 1
                    except Exception as e:
                        self.stderr.write(f"Row {row_num}: Error updating {username}: {e}")
                        errors += 1

            self.stdout.write(f"Bulk update summary:")
            self.stdout.write(f"  Users updated: {updated}")
            if errors > 0:
                self.stdout.write(f"  Errors encountered: {errors}")

        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_file}")
        except Exception as e:
            raise CommandError(f"Error processing CSV file: {e}")

    def handle_clean(self, options: Dict[str, Any]) -> None:
        """Clean up placeholder emails by checking LMS for real emails."""
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write("DRY RUN: No changes will be made")

        # This is essentially the same as the update action
        self.stdout.write("Cleaning up placeholder emails...")
        self.handle_update(options)