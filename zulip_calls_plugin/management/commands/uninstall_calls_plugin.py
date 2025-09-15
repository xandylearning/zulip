import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Uninstall the Zulip Calls Plugin"

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-data",
            action="store_true",
            help="Keep database tables and data (only remove from settings)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force uninstall even if data exists",
        )

    def handle(self, *args, **options):
        self.stdout.write("Uninstalling Zulip Calls Plugin...")

        # Check if plugin is installed
        if "zulip_calls_plugin" not in settings.INSTALLED_APPS:
            self.stdout.write(
                self.style.WARNING("Plugin is not currently installed.")
            )
            return

        try:
            # Step 1: Check for existing data
            if not options["keep_data"] and not options["force"]:
                self.check_existing_data()

            # Step 2: Remove database tables if requested
            if not options["keep_data"]:
                self.remove_database_tables()

            # Step 3: Remove from INSTALLED_APPS
            self.remove_from_installed_apps()

            # Step 4: Remove URL patterns
            self.remove_url_patterns()

            # Step 5: Remove injected script
            self.remove_script()

            self.stdout.write(
                self.style.SUCCESS("✅ Zulip Calls Plugin uninstalled successfully!")
            )

            if options["keep_data"]:
                self.stdout.write(
                    self.style.WARNING("⚠️  Database tables preserved. Use 'python manage.py migrate zulip_calls_plugin zero' to remove them.")
                )

        except Exception as e:
            raise CommandError(f"Uninstallation failed: {e}")

    def check_existing_data(self):
        """Check if there's existing call data"""
        try:
            from zulip_calls_plugin.models import Call
            call_count = Call.objects.count()

            if call_count > 0:
                raise CommandError(
                    f"Found {call_count} existing calls. Use --keep-data to preserve them or --force to delete all data."
                )

        except Exception as e:
            # If we can't check (e.g., tables don't exist), that's fine
            pass

    def remove_database_tables(self):
        """Remove database tables by running migrations backward"""
        self.stdout.write("🗄️  Removing database tables...")

        from django.core.management import call_command

        try:
            # Run migrations backward to remove tables
            call_command("migrate", "zulip_calls_plugin", "zero", verbosity=1)
            self.stdout.write("   ✅ Database tables removed")
        except Exception as e:
            self.stdout.write(f"   ⚠️  Failed to remove database tables: {e}")

    def remove_from_installed_apps(self):
        """Remove plugin from INSTALLED_APPS in settings"""
        self.stdout.write("📦 Removing from INSTALLED_APPS...")

        settings_file = os.path.join(settings.BASE_DIR, "zproject", "computed_settings.py")

        if not os.path.exists(settings_file):
            settings_file = os.path.join(settings.BASE_DIR, "zproject", "settings.py")

        try:
            with open(settings_file, "r") as f:
                content = f.read()

            # Remove the plugin line
            lines = content.split('\n')
            new_lines = []

            for line in lines:
                if '"zulip_calls_plugin"' not in line:
                    new_lines.append(line)
                else:
                    self.stdout.write(f"   🗑️  Removing: {line.strip()}")

            with open(settings_file, "w") as f:
                f.write('\n'.join(new_lines))

            self.stdout.write("   ✅ Removed from INSTALLED_APPS")

        except Exception as e:
            self.stdout.write(f"   ⚠️  Could not modify settings automatically: {e}")
            self.stdout.write("   🔧 Please manually remove 'zulip_calls_plugin' from INSTALLED_APPS")

    def remove_url_patterns(self):
        """Remove URL patterns from main URLconf"""
        self.stdout.write("🔗 Removing URL patterns...")

        urls_file = os.path.join(settings.BASE_DIR, "zproject", "urls.py")

        try:
            with open(urls_file, "r") as f:
                content = f.read()

            # Remove plugin-related lines
            lines = content.split('\n')
            new_lines = []

            for line in lines:
                if "zulip_calls_plugin" not in line and "CallsPluginConfig" not in line:
                    new_lines.append(line)
                else:
                    self.stdout.write(f"   🗑️  Removing: {line.strip()}")

            with open(urls_file, "w") as f:
                f.write('\n'.join(new_lines))

            self.stdout.write("   ✅ Removed URL patterns")

        except Exception as e:
            self.stdout.write(f"   ⚠️  Could not modify URLs automatically: {e}")
            self.stdout.write("   🔧 Please manually remove plugin URLs from zproject/urls.py")

    def remove_script(self):
        """Remove injected script from main template"""
        self.stdout.write("📄 Removing embedded calls script...")

        try:
            from zulip_calls_plugin.integration import remove_embedded_calls_script
            success = remove_embedded_calls_script()

            if success:
                self.stdout.write("   ✅ Script removed successfully")
            else:
                self.stdout.write("   ⚠️  Script removal failed")

        except Exception as e:
            self.stdout.write(f"   ⚠️  Script removal failed: {e}")

    def style_success(self, message):
        """Style success messages"""
        return f"\033[92m{message}\033[0m"

    def style_warning(self, message):
        """Style warning messages"""
        return f"\033[93m{message}\033[0m"