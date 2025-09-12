#!/usr/bin/env python3
"""
Setup script for the Event Listeners Django App Plugin.

This script helps with installing and configuring the event listeners plugin
in an existing Zulip installation.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any

# Configuration templates
SETTINGS_TEMPLATE = '''
# =============================================================================
# EVENT LISTENERS PLUGIN CONFIGURATION
# =============================================================================

# Enable the event listeners plugin
EVENT_LISTENERS_ENABLED = True

# Add to INSTALLED_APPS if not already present
if 'zerver.event_listeners' not in INSTALLED_APPS:
    INSTALLED_APPS.append('zerver.event_listeners')

# Event listener configuration
EVENT_LISTENERS_CONFIG = {
    'DEFAULT_LISTENERS': [
        'message_logger',
        'user_status_tracker',
        'stream_activity_monitor',
    ],
    'QUEUE_CONFIG': {
        'max_retries': 3,
        'retry_delay': 5,
        'batch_size': 100,
    },
    'LOGGING': {
        'level': 'INFO',
        'file': None,  # Set to file path for file logging
    },
    'STATISTICS': {
        'enabled': True,
        'retention_days': 30,
    },
}

# Add logging configuration
LOGGING['loggers']['zerver.event_listeners'] = {
    'handlers': ['console'],
    'level': 'INFO',
    'propagate': False,
}
'''

SYSTEMD_SERVICE_TEMPLATE = '''[Unit]
Description=Zulip Event Listeners
After=network.target zulip.service
Requires=zulip.service

[Service]
Type=simple
User=zulip
Group=zulip
WorkingDirectory={zulip_path}
Environment="DJANGO_SETTINGS_MODULE=zproject.settings"
ExecStart={python_path} {manage_py} run_event_listeners
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
'''

DOCKER_COMPOSE_TEMPLATE = '''
  # Event Listeners Service
  event-listeners:
    build: .
    depends_on:
      - database
      - memcached
      - rabbitmq
    environment:
      - DJANGO_SETTINGS_MODULE=zproject.settings
      - EVENT_LISTENERS_ENABLED=true
    command: python manage.py run_event_listeners
    volumes:
      - ".:/app"
    restart: unless-stopped
'''


class EventListenersInstaller:
    """Installer for the Event Listeners plugin"""
    
    def __init__(self, zulip_path: str = None):
        self.zulip_path = Path(zulip_path or os.getcwd())
        self.manage_py = self.zulip_path / "manage.py"
        self.settings_dir = self.zulip_path / "zproject"
        
        if not self.manage_py.exists():
            raise ValueError(f"Zulip manage.py not found at {self.manage_py}")
    
    def install(self, config: Dict[str, Any] = None) -> None:
        """Install the event listeners plugin"""
        print("🚀 Installing Event Listeners Plugin...")
        
        config = config or {}
        
        # Step 1: Check prerequisites
        self.check_prerequisites()
        
        # Step 2: Run migrations
        self.run_migrations()
        
        # Step 3: Configure settings
        if config.get('configure_settings', True):
            self.configure_settings()
        
        # Step 4: Create example listeners
        if config.get('create_examples', True):
            self.create_example_listeners()
        
        # Step 5: Setup service (optional)
        if config.get('setup_service', False):
            self.setup_service(config.get('service_type', 'systemd'))
        
        print("✅ Event Listeners Plugin installed successfully!")
        self.print_next_steps()
    
    def check_prerequisites(self) -> None:
        """Check system prerequisites"""
        print("🔍 Checking prerequisites...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            raise RuntimeError("Python 3.8+ required")
        
        # Check Django
        try:
            import django
            if django.VERSION < (3, 2):
                raise RuntimeError("Django 3.2+ required")
        except ImportError:
            raise RuntimeError("Django not found")
        
        # Check Zulip components
        zerver_path = self.zulip_path / "zerver"
        if not zerver_path.exists():
            raise RuntimeError(f"Zulip zerver directory not found at {zerver_path}")
        
        print("✅ Prerequisites check passed")
    
    def run_migrations(self) -> None:
        """Run Django migrations for the plugin"""
        print("🗄️  Running database migrations...")
        
        try:
            result = subprocess.run([
                sys.executable, str(self.manage_py), 
                "migrate", "event_listeners"
            ], cwd=self.zulip_path, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Migration output: {result.stdout}")
                print(f"Migration errors: {result.stderr}")
                raise RuntimeError("Migration failed")
            
            print("✅ Migrations completed successfully")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise
    
    def configure_settings(self) -> None:
        """Configure Django settings"""
        print("⚙️  Configuring settings...")
        
        settings_file = self.settings_dir / "dev_settings.py"
        if not settings_file.exists():
            settings_file = self.settings_dir / "settings.py"
        
        if not settings_file.exists():
            print("⚠️  No settings file found. Please manually add configuration.")
            return
        
        # Check if already configured
        content = settings_file.read_text()
        if "EVENT_LISTENERS_ENABLED" in content:
            print("✅ Settings already configured")
            return
        
        # Backup original
        backup_file = settings_file.with_suffix(".py.backup")
        shutil.copy2(settings_file, backup_file)
        print(f"📋 Settings backed up to {backup_file}")
        
        # Append configuration
        with settings_file.open("a") as f:
            f.write(SETTINGS_TEMPLATE)
        
        print("✅ Settings configured successfully")
    
    def create_example_listeners(self) -> None:
        """Create example event listeners"""
        print("📝 Creating example listeners...")
        
        examples_dir = self.zulip_path / "zerver" / "event_listeners" / "examples"
        if examples_dir.exists():
            print("✅ Example listeners already exist")
            return
        
        # The examples.py file was already created, so just verify it exists
        examples_file = self.zulip_path / "zerver" / "event_listeners" / "examples.py"
        if examples_file.exists():
            print("✅ Example listeners created")
        else:
            print("⚠️  Example listeners file not found")
    
    def setup_service(self, service_type: str = "systemd") -> None:
        """Setup system service"""
        print(f"🛠️  Setting up {service_type} service...")
        
        if service_type == "systemd":
            self.setup_systemd_service()
        elif service_type == "docker":
            self.setup_docker_service()
        else:
            print(f"⚠️  Unknown service type: {service_type}")
    
    def setup_systemd_service(self) -> None:
        """Setup systemd service"""
        python_path = sys.executable
        zulip_path = str(self.zulip_path)
        manage_py = str(self.manage_py)
        
        service_content = SYSTEMD_SERVICE_TEMPLATE.format(
            python_path=python_path,
            zulip_path=zulip_path,
            manage_py=manage_py
        )
        
        service_file = Path("/tmp/zulip-event-listeners.service")
        service_file.write_text(service_content)
        
        print(f"📄 Systemd service file created: {service_file}")
        print("To install the service, run:")
        print(f"  sudo cp {service_file} /etc/systemd/system/")
        print("  sudo systemctl daemon-reload")
        print("  sudo systemctl enable zulip-event-listeners")
        print("  sudo systemctl start zulip-event-listeners")
    
    def setup_docker_service(self) -> None:
        """Setup Docker Compose service"""
        compose_file = self.zulip_path / "docker-compose.yml"
        
        if compose_file.exists():
            content = compose_file.read_text()
            if "event-listeners:" in content:
                print("✅ Docker Compose already configured")
                return
            
            # Append service configuration
            with compose_file.open("a") as f:
                f.write(DOCKER_COMPOSE_TEMPLATE)
            
            print("✅ Docker Compose service added")
        else:
            print("⚠️  docker-compose.yml not found")
    
    def print_next_steps(self) -> None:
        """Print next steps for the user"""
        print("\n" + "="*60)
        print("🎉 INSTALLATION COMPLETE!")
        print("="*60)
        print("\nNext steps:")
        print("1. Test the installation:")
        print("   ./manage.py list_event_listeners")
        print("\n2. Run event listeners:")
        print("   ./manage.py run_event_listeners")
        print("\n3. Run specific listeners:")
        print("   ./manage.py run_event_listeners --listeners message_logger")
        print("\n4. View documentation:")
        print("   cat zerver/event_listeners/README.md")
        print("\n5. Create custom listeners:")
        print("   See examples in zerver/event_listeners/examples.py")
        print("\n6. Monitor logs:")
        print("   tail -f /var/log/zulip/event_listeners.log")
        print("\n" + "="*60)


def main():
    """Main installation function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Install Event Listeners Plugin")
    parser.add_argument("--zulip-path", help="Path to Zulip installation")
    parser.add_argument("--no-settings", action="store_true", 
                       help="Skip settings configuration")
    parser.add_argument("--no-examples", action="store_true",
                       help="Skip creating examples")
    parser.add_argument("--setup-service", choices=["systemd", "docker"],
                       help="Setup system service")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without doing it")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    
    try:
        installer = EventListenersInstaller(args.zulip_path)
        
        config = {
            'configure_settings': not args.no_settings,
            'create_examples': not args.no_examples,
            'setup_service': bool(args.setup_service),
            'service_type': args.setup_service,
        }
        
        if not args.dry_run:
            installer.install(config)
        else:
            print("Would install Event Listeners Plugin with config:", config)
            
    except Exception as e:
        print(f"❌ Installation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()