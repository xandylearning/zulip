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

# Source the environment file created by configure-cloudrun-settings
ENV_FILE="/etc/zulip/cloudrun.env"
if [ -f "$ENV_FILE" ]; then
    echo "Sourcing Cloud Run environment variables from $ENV_FILE..."
    source "$ENV_FILE"
else
    echo "Warning: Environment file $ENV_FILE not found"
fi

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

# Configure supervisor based on the command
case "${1:-app:run}" in
    "app:run")
        echo "Starting Zulip application server..."
        exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/zulip.conf
        ;;
    "app:worker")
        echo "Starting Zulip worker processes only..."
        # Start only worker processes, not the web server
        exec su zulip -c '/root/zulip/manage.py process_queue --all'
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
