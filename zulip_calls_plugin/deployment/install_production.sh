#!/bin/bash
set -e

# Zulip Calls Plugin - Production Installation Script
# Usage: ./install_production.sh [--dry-run]

ZULIP_PATH="/srv/zulip"
PLUGIN_NAME="zulip_calls_plugin"
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_command() {
    local cmd="$1"
    local desc="$2"

    log_info "$desc"

    if [ "$DRY_RUN" = true ]; then
        echo "DRY RUN: $cmd"
        return 0
    fi

    if eval "$cmd"; then
        log_success "$desc completed"
    else
        log_error "$desc failed"
        exit 1
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if running as root or with sudo
    if [[ $EUID -ne 0 ]] && ! sudo -n true 2>/dev/null; then
        log_error "This script requires root privileges or passwordless sudo"
        exit 1
    fi

    # Check if Zulip directory exists
    if [ ! -d "$ZULIP_PATH" ]; then
        log_error "Zulip directory not found at $ZULIP_PATH"
        exit 1
    fi

    # Check if plugin directory exists
    if [ ! -d "$PLUGIN_NAME" ]; then
        log_error "Plugin directory $PLUGIN_NAME not found in current directory"
        log_info "Please run this script from the directory containing the plugin"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

backup_files() {
    log_info "Creating backup of Zulip configuration files..."

    local backup_dir="/tmp/zulip_backup_$(date +%Y%m%d_%H%M%S)"

    run_command "mkdir -p $backup_dir" "Creating backup directory"
    run_command "cp $ZULIP_PATH/zproject/prod_settings.py $backup_dir/" "Backing up prod_settings.py"
    run_command "cp $ZULIP_PATH/zproject/urls.py $backup_dir/" "Backing up urls.py"
    run_command "cp $ZULIP_PATH/templates/zerver/app.html $backup_dir/" "Backing up app.html"

    echo "$backup_dir" > /tmp/zulip_calls_backup_path
    log_success "Backup created at $backup_dir"
}

install_plugin_files() {
    log_info "Installing plugin files..."

    # Copy plugin to Zulip directory
    run_command "sudo -u zulip cp -r $PLUGIN_NAME $ZULIP_PATH/" "Copying plugin files"

    # Set correct permissions
    run_command "sudo chown -R zulip:zulip $ZULIP_PATH/$PLUGIN_NAME" "Setting file permissions"
}

update_settings() {
    log_info "Updating Zulip settings..."

    local settings_file="$ZULIP_PATH/zproject/prod_settings.py"

    # Check if already added
    if grep -q "$PLUGIN_NAME" "$settings_file"; then
        log_warning "Plugin already in INSTALLED_APPS"
        return 0
    fi

    # Add to INSTALLED_APPS
    local temp_file=$(mktemp)
    cat "$settings_file" > "$temp_file"
    echo "" >> "$temp_file"
    echo "# Zulip Calls Plugin" >> "$temp_file"
    echo "INSTALLED_APPS += [\"$PLUGIN_NAME\"]" >> "$temp_file"

    run_command "sudo cp $temp_file $settings_file" "Adding plugin to INSTALLED_APPS"
    run_command "sudo chown zulip:zulip $settings_file" "Setting settings file permissions"
    rm "$temp_file"
}

update_urls() {
    log_info "Updating URL configuration..."

    local urls_file="$ZULIP_PATH/zproject/urls.py"

    # Check if already added
    if grep -q "calls_urls" "$urls_file"; then
        log_warning "Plugin URLs already configured"
        return 0
    fi

    # Create modified URLs file
    local temp_file=$(mktemp)

    # Add import after other imports
    sed '/^from django.urls import/a from zulip_calls_plugin.urls import urlpatterns as calls_urls' "$urls_file" > "$temp_file"

    # Add URL patterns before the last closing bracket
    sed '/^]$/i\    # Zulip Calls Plugin URLs\n    path("", include(calls_urls)),' "$temp_file" > "${temp_file}.2"

    run_command "sudo cp ${temp_file}.2 $urls_file" "Adding plugin URLs"
    run_command "sudo chown zulip:zulip $urls_file" "Setting URLs file permissions"
    rm "$temp_file" "${temp_file}.2"
}

update_template() {
    log_info "Updating app template..."

    local template_file="$ZULIP_PATH/templates/zerver/app.html"

    # Check if already added
    if grep -q "calls/script" "$template_file"; then
        log_warning "Plugin JavaScript already configured"
        return 0
    fi

    # Add JavaScript before closing body tag
    local temp_file=$(mktemp)
    sed '/^<\/body>/i\<!-- Zulip Calls Plugin -->\n<script>\nif (typeof page_params !== "undefined") {\n    fetch("/calls/script")\n        .then(response => response.text())\n        .then(html => {\n            document.head.insertAdjacentHTML("beforeend", html);\n        })\n        .catch(err => console.log("Embedded calls not available"));\n}\n</script>' "$template_file" > "$temp_file"

    run_command "sudo cp $temp_file $template_file" "Adding plugin JavaScript"
    run_command "sudo chown zulip:zulip $template_file" "Setting template file permissions"
    rm "$temp_file"
}

run_migrations() {
    log_info "Running database migrations..."

    run_command "sudo -u zulip $ZULIP_PATH/manage.py makemigrations $PLUGIN_NAME" "Creating migrations"
    run_command "sudo -u zulip $ZULIP_PATH/manage.py migrate $PLUGIN_NAME" "Applying migrations"
}

collect_static() {
    log_info "Collecting static files..."

    run_command "sudo -u zulip $ZULIP_PATH/manage.py collectstatic --noinput" "Collecting static files"
}

restart_services() {
    log_info "Restarting Zulip services..."

    run_command "sudo supervisorctl restart zulip-django" "Restarting Django"
    run_command "sudo supervisorctl restart zulip-tornado" "Restarting Tornado"

    # Wait for services to start
    sleep 5

    # Check if services are running
    if sudo supervisorctl status zulip-django | grep -q RUNNING; then
        log_success "Django service is running"
    else
        log_error "Django service failed to start"
        exit 1
    fi

    if sudo supervisorctl status zulip-tornado | grep -q RUNNING; then
        log_success "Tornado service is running"
    else
        log_error "Tornado service failed to start"
        exit 1
    fi
}

test_installation() {
    log_info "Testing installation..."

    # Test if plugin endpoints are accessible
    local test_url="http://localhost/calls/script"

    if curl -s -o /dev/null -w "%{http_code}" "$test_url" | grep -q "200"; then
        log_success "Plugin endpoints are accessible"
    else
        log_warning "Plugin endpoints may not be accessible yet (this might be normal)"
    fi

    # Test database tables
    if sudo -u zulip $ZULIP_PATH/manage.py shell -c "from zulip_calls_plugin.models import Call; print('Plugin models loaded successfully')" 2>/dev/null; then
        log_success "Plugin database models are working"
    else
        log_error "Plugin database models failed to load"
        exit 1
    fi
}

print_success_message() {
    echo ""
    echo "======================================================"
    log_success "🎉 Zulip Calls Plugin Installation Complete!"
    echo "======================================================"
    echo ""
    echo "📞 Available Endpoints:"
    echo "   • POST /api/v1/calls/create-embedded - Create embedded calls"
    echo "   • GET  /calls/embed/{id} - Embedded call interface"
    echo "   • GET  /calls/script - Plugin JavaScript"
    echo ""
    echo "🧪 Test the installation:"
    echo "   1. Open your Zulip web interface"
    echo "   2. Start a direct message"
    echo "   3. Click the video or audio call button"
    echo "   4. Embedded call window should open!"
    echo ""
    echo "📁 Backup location: $(cat /tmp/zulip_calls_backup_path 2>/dev/null || echo 'No backup created')"
    echo ""
    echo "🔧 To uninstall: ./uninstall_production.sh"
    echo "======================================================"
}

main() {
    log_info "Starting Zulip Calls Plugin production installation..."

    check_prerequisites
    backup_files
    install_plugin_files
    update_settings
    update_urls
    update_template
    run_migrations
    collect_static
    restart_services
    test_installation
    print_success_message
}

# Run main function
main "$@"