import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Install the Zulip Calls Plugin"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force installation even if already installed",
        )

    def handle(self, *args, **options):
        self.stdout.write("Installing Zulip Calls Plugin...")
        self.options = options  # Store options for use in other methods

        # Check if already installed
        if "zulip_calls_plugin" in settings.INSTALLED_APPS and not options["force"]:
            raise CommandError("Plugin is already installed. Use --force to reinstall.")

        try:
            # Step 1: Add to INSTALLED_APPS
            self.add_to_installed_apps()

            # Step 2: Add URL patterns
            self.add_url_patterns()

            # Step 3: Create and run migrations
            self.create_migrations()

            # Step 4: Apply migrations
            self.apply_migrations()

            # Step 5: Inject embedded calls script
            self.inject_script()

            self.stdout.write(
                self.style.SUCCESS("✅ Zulip Calls Plugin installed successfully!")
            )

            self.stdout.write("\n" + "="*50)
            self.stdout.write("📋 INSTALLATION COMPLETE")
            self.stdout.write("="*50)
            self.stdout.write("\n📞 Available Endpoints:")
            self.stdout.write("   • POST /api/v1/calls/initiate - Quick call creation")
            self.stdout.write("   • POST /api/v1/calls/create - Full call creation")
            self.stdout.write("   • POST /api/v1/calls/<id>/respond - Accept/decline call")
            self.stdout.write("   • POST /api/v1/calls/<id>/end - End call")
            self.stdout.write("   • GET  /api/v1/calls/<id>/status - Get call status")
            self.stdout.write("   • GET  /api/v1/calls/history - Get call history")

            self.stdout.write("\n🧪 Test with curl:")
            self.stdout.write('   curl -X POST "http://localhost:9991/api/v1/calls/initiate" \\')
            self.stdout.write('     -u "user@example.com:api-key" \\')
            self.stdout.write('     -d "recipient_email=recipient@example.com" \\')
            self.stdout.write('     -d "is_video_call=true"')

            self.stdout.write("\n🔧 To uninstall: python manage.py uninstall_calls_plugin")
            self.stdout.write("="*50)

        except Exception as e:
            raise CommandError(f"Installation failed: {e}")

    def add_to_installed_apps(self):
        """Add plugin to INSTALLED_APPS in settings"""
        self.stdout.write("📦 Adding to INSTALLED_APPS...")

        # Find Zulip root directory - we're in /srv/zulip/zulip_calls_plugin/management/commands/
        # Need to go up to /srv/zulip/
        plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        zulip_root = os.path.dirname(plugin_dir)  # Go up one more level to /srv/zulip/
        settings_file = os.path.join(zulip_root, "zproject", "computed_settings.py")

        if self.options.get('verbosity', 1) >= 2:
            self.stdout.write(f"   Debug: Plugin dir: {plugin_dir}")
            self.stdout.write(f"   Debug: Zulip root: {zulip_root}")
            self.stdout.write(f"   Debug: Settings file: {settings_file}")

        if not os.path.exists(settings_file):
            # Fallback to settings.py if computed_settings doesn't exist
            settings_file = os.path.join(zulip_root, "zproject", "settings.py")
            if not os.path.exists(settings_file):
                # Try production settings
                settings_file = os.path.join(zulip_root, "zproject", "prod_settings.py")

        try:
            with open(settings_file, "r") as f:
                content = f.read()

            # Check if plugin is already in the file
            if "zulip_calls_plugin" not in content:
                # Find INSTALLED_APPS and add our plugin
                if "INSTALLED_APPS" in content:
                    # Add plugin to the list
                    import_line = '    "zulip_calls_plugin",\n'

                    # Find the INSTALLED_APPS section and add our plugin
                    lines = content.split('\n')
                    new_lines = []
                    in_installed_apps = False

                    for line in lines:
                        new_lines.append(line)
                        if "INSTALLED_APPS" in line and "=" in line:
                            in_installed_apps = True
                        elif in_installed_apps and line.strip().startswith('"') and line.strip().endswith('",'):
                            # Add our plugin after the last app
                            if "zerver" in line:  # Add after zerver app
                                new_lines.append('    "zulip_calls_plugin",')
                                in_installed_apps = False

                    # Write back the modified content
                    with open(settings_file, "w") as f:
                        f.write('\n'.join(new_lines))

                    self.stdout.write("   ✅ Added to INSTALLED_APPS")
                else:
                    self.stdout.write("   ⚠️  INSTALLED_APPS not found in settings file")
            else:
                self.stdout.write("   ℹ️  Already in INSTALLED_APPS")

        except Exception as e:
            self.stdout.write(f"   ⚠️  Could not modify settings file automatically: {e}")
            self.stdout.write("   🔧 Please manually add 'zulip_calls_plugin' to INSTALLED_APPS")

    def add_url_patterns(self):
        """Add URL patterns to main URLconf"""
        self.stdout.write("🔗 Adding URL patterns...")

        # Find Zulip root directory - we're in /srv/zulip/zulip_calls_plugin/management/commands/
        # Need to go up to /srv/zulip/
        plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        zulip_root = os.path.dirname(plugin_dir)  # Go up one more level to /srv/zulip/
        urls_file = os.path.join(zulip_root, "zproject", "urls.py")

        try:
            with open(urls_file, "r") as f:
                content = f.read()

            if "zulip_calls_plugin" not in content:
                # Add import and URL patterns
                import_line = "from zulip_calls_plugin.plugin_config import CallsPluginConfig\n"
                url_line = "    # Zulip Calls Plugin URLs\n    path('', include(CallsPluginConfig.get_url_patterns())),\n"

                lines = content.split('\n')
                new_lines = []

                # Add import after other imports
                for i, line in enumerate(lines):
                    new_lines.append(line)
                    if line.startswith("from ") and "import" in line and i < 20:
                        # Add our import after other imports
                        if "zulip_calls_plugin" not in '\n'.join(lines[i:i+5]):
                            new_lines.append(import_line.rstrip())
                            break

                # Add URL pattern in urlpatterns
                for i, line in enumerate(new_lines):
                    if "urlpatterns = [" in line:
                        # Find a good place to insert (after existing patterns)
                        j = i + 1
                        while j < len(new_lines) and not new_lines[j].strip().startswith("]"):
                            j += 1
                        # Insert before the closing bracket
                        new_lines.insert(j, url_line.rstrip())
                        break

                with open(urls_file, "w") as f:
                    f.write('\n'.join(new_lines))

                self.stdout.write("   ✅ Added URL patterns")
            else:
                self.stdout.write("   ℹ️  URL patterns already added")

        except Exception as e:
            self.stdout.write(f"   ⚠️  Could not modify URLs automatically: {e}")
            self.stdout.write("   🔧 Please manually add plugin URLs to zproject/urls.py")

    def create_migrations(self):
        """Create database migrations for the plugin"""
        self.stdout.write("🗄️  Creating database migrations...")

        from django.core.management import call_command

        try:
            call_command("makemigrations", "zulip_calls_plugin", verbosity=1)
            self.stdout.write("   ✅ Migrations created")
        except Exception as e:
            self.stdout.write(f"   ⚠️  Migration creation failed: {e}")

    def apply_migrations(self):
        """Apply database migrations"""
        self.stdout.write("🔄 Applying database migrations...")

        from django.core.management import call_command

        try:
            # First add the plugin to Django's app registry if it's not already there
            from django.apps import apps
            if not apps.is_installed('zulip_calls_plugin'):
                self.stdout.write("   ℹ️  Plugin not in INSTALLED_APPS yet, skipping migration")
                self.stdout.write("   🔧 Please restart Django and run migrations manually:")
                self.stdout.write("       python manage.py migrate zulip_calls_plugin")
                return

            call_command("migrate", "zulip_calls_plugin", verbosity=1)
            self.stdout.write("   ✅ Migrations applied")
        except Exception as e:
            self.stdout.write(f"   ⚠️  Migration application failed: {e}")
            self.stdout.write("   🔧 Please run migrations manually after adding to INSTALLED_APPS:")
            self.stdout.write("       python manage.py migrate zulip_calls_plugin")

    def inject_script(self):
        """Inject embedded calls script into main template"""
        self.stdout.write("📄 Injecting embedded calls script...")

        try:
            from zulip_calls_plugin.integration import inject_embedded_calls_script
            success = inject_embedded_calls_script()

            if success:
                self.stdout.write("   ✅ Script injected successfully")
            else:
                self.stdout.write("   ⚠️  Script injection failed")

        except Exception as e:
            self.stdout.write(f"   ⚠️  Script injection failed: {e}")