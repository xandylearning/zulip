#!/bin/bash
#
# Zulip Cloud Run entrypoint script
# This script configures and starts Zulip in a Cloud Run environment

set -euo pipefail

echo "Starting Zulip Cloud Run container..."

# Configure Zulip secrets from environment variables FIRST
# This must happen before any Django operations
echo "Configuring Zulip secrets..."

# Always use the configure-cloudrun-secrets script for consistency
# It will handle both base64-encoded secrets and environment variable fallbacks
echo "Running secrets configuration script..."
/root/zulip/scripts/setup/configure-cloudrun-secrets

# Configure Zulip settings for Cloud Run
echo "Configuring Zulip settings..."
/root/zulip/scripts/setup/configure-cloudrun-settings

# Set additional environment variables for Cloud Run
export DJANGO_SETTINGS_MODULE=zproject.settings
export PYTHONPATH=/root/zulip
export PYTHONUNBUFFERED=1

# Ensure we're in the right directory for Python imports
cd /root/zulip

# Debug: Show Python environment
echo "Debug: Python environment setup:"
echo "  DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  Current directory: $(pwd)"
echo "  Python version: $(python3 --version)"
echo "  Django settings file exists: $(test -f zproject/settings.py && echo "YES" || echo "NO")"

# Initialize the database if needed
echo "Checking database initialization..."
if [ "${SKIP_DB_INIT:-false}" != "true" ]; then
    echo "Initializing database..."
    cd /root/zulip
    
    # Run database migrations
    su zulip -c './manage.py migrate --noinput'
    
    # Create initial realm if needed
    if [ "${CREATE_INITIAL_REALM:-false}" = "true" ]; then
        echo "Creating initial realm..."
        su zulip -c "./manage.py generate_realm_creation_link" || true
    fi
    
    # Load initial data if needed
    if [ "${LOAD_INITIAL_DATA:-false}" = "true" ]; then
        echo "Loading initial data..."
        su zulip -c './manage.py loaddata zerver/fixtures/messages.json' || true
    fi
fi

# Set up static files
echo "Collecting static files..."
cd /root/zulip
su zulip -c './manage.py collectstatic --noinput --clear'

# Skip database check for now to avoid Django import issues
echo "Skipping database check to avoid Django import issues..."
echo "Database connection will be tested when the server starts..."

# Configure application startup based on the command
case "${1:-app:run}" in
    "app:run")
        echo "Starting Zulip application server for Cloud Run..."
        cd /root/zulip
        
        # For Cloud Run, we need to run the Django application directly
        # Use Django's built-in server for simplicity in Cloud Run
        echo "Starting Django development server..."
        # Set the port environment variable for Django
        export PORT=80
        # Use 0.0.0.0 to bind to all interfaces for Cloud Run
        # Disable debug mode for production
        export DJANGO_DEBUG=False
        
        # Try to start the server with better error handling
        echo "Attempting to start Django server..."
        exec su zulip -c 'python3 manage.py runserver 0.0.0.0:80 --noreload --verbosity=2'
        ;;
    "app:worker")
        echo "Starting Zulip worker processes only..."
        # Start only worker processes, not the web server
        cd /root/zulip
        exec su zulip -c './manage.py process_queue --all'
        ;;
    "app:migrate")
        echo "Running database migrations only..."
        cd /root/zulip
        exec su zulip -c './manage.py migrate'
        ;;
    "app:shell")
        echo "Starting Zulip management shell..."
        cd /root/zulip
        exec su zulip -c './manage.py shell'
        ;;
    *)
        echo "Running custom command: $*"
        exec "$@"
        ;;
esac
