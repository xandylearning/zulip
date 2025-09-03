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

# Test database connection before starting the server
echo "Testing database connection..."
if ! su zulip -c './manage.py check --database default'; then
    echo "ERROR: Database connection test failed!"
    echo "Please check your database configuration and try again."
    exit 1
fi
echo "Database connection test passed!"

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
        exec su zulip -c 'python3 manage.py runserver 0.0.0.0:80 --noreload'
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
